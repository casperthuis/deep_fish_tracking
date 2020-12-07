import torch
from addict import Dict
from mmdet.core.bbox.transforms import bbox_cxcywh_to_xyxy, bbox_xyxy_to_cxcywh
from mmdet.models.builder import build_backbone, build_head, build_neck

from ..builder import MODELS
from .base import BaseSingleObjectTracker


@MODELS.register_module()
class SiamRPN(BaseSingleObjectTracker):

    def __init__(self,
                 pretrains=None,
                 backbone=None,
                 neck=None,
                 head=None,
                 frozen_modules=None,
                 train_cfg=None,
                 test_cfg=None):
        super(SiamRPN, self).__init__()
        self.backbone = build_backbone(backbone)
        if neck is not None:
            self.neck = build_neck(neck)
        head = head.copy()
        head.update(train_cfg=None, test_cfg=test_cfg.rpn)
        self.head = build_head(head)

        self.test_cfg = test_cfg
        self.train_cfg = train_cfg

        self.init_weights(pretrains)
        if frozen_modules is not None:
            self.freeze_module(frozen_modules)

    def init_weights(self, pretrain):
        if pretrain is None:
            pretrain = dict()
        assert isinstance(pretrain, dict), '`pretrain` must be a dict.'
        if self.with_backbone and pretrain.get('backbone', False):
            self.init_module('backbone', pretrain['backbone'])

    def forward_template(self, z_img):
        z_feat = self.backbone(z_img)
        if self.with_neck:
            z_feat = self.neck(z_feat)

        z_feat_center = []
        for i in range(len(z_feat)):
            left = (z_feat[i].size(3) - self.test_cfg.center_size) // 2
            right = left + self.test_cfg.center_size
            z_feat_center.append(z_feat[i][:, :, left:right, left:right])
        return tuple(z_feat_center)

    def forward_search(self, x_img):
        x_feat = self.backbone(x_img)
        if self.with_neck:
            x_feat = self.neck(x_feat)
        return x_feat

    def get_cropped_img(self, img, center_xy, target_size, crop_size,
                        avg_channel):
        N, C, H, W = img.shape
        context_xmin = int(center_xy[0] - crop_size / 2)
        context_xmax = int(center_xy[0] + crop_size / 2)
        context_ymin = int(center_xy[1] - crop_size / 2)
        context_ymax = int(center_xy[1] + crop_size / 2)

        left_pad = max(0, -context_xmin)
        top_pad = max(0, -context_ymin)
        right_pad = max(0, context_xmax - W)
        bottom_pad = max(0, context_ymax - H)

        context_xmin += left_pad
        context_xmax += left_pad
        context_ymin += top_pad
        context_ymax += top_pad

        avg_channel = avg_channel[:, None, None]
        if any([top_pad, bottom_pad, left_pad, right_pad]):
            new_img = img.new_zeros(N, C, H + top_pad + bottom_pad,
                                    W + left_pad + right_pad)
            new_img[..., top_pad:top_pad + H, left_pad:left_pad + W] = img
            if top_pad:
                new_img[..., :top_pad, left_pad:left_pad + W] = avg_channel
            if bottom_pad:
                new_img[..., H + top_pad:, left_pad:left_pad + W] = avg_channel
            if left_pad:
                new_img[..., :left_pad] = avg_channel
            if right_pad:
                new_img[..., W + left_pad:] = avg_channel
            crop_img = new_img[..., context_ymin:context_ymax + 1,
                               context_xmin:context_xmax + 1]
        else:
            crop_img = img[..., context_ymin:context_ymax + 1,
                           context_xmin:context_xmax + 1]

        if target_size != crop_size:
            crop_img = torch.nn.functional.interpolate(
                crop_img,
                size=(target_size, target_size),
                mode='bilinear',
                align_corners=False)
        return crop_img

    def _bbox_clip(self, bbox, img_h, img_w):
        bbox[0] = bbox[0].clamp(0., img_w)
        bbox[1] = bbox[1].clamp(0., img_h)
        bbox[2] = bbox[2].clamp(10., img_w)
        bbox[3] = bbox[3].clamp(10., img_h)
        return bbox

    def init(self, img, bbox):
        z_width = bbox[2] + self.test_cfg.context_amount * (bbox[2] + bbox[3])
        z_height = bbox[3] + self.test_cfg.context_amount * (bbox[2] + bbox[3])
        z_size = torch.round(torch.sqrt(z_width * z_height))
        avg_channel = torch.mean(img, dim=(0, 2, 3))
        z_crop = self.get_cropped_img(img, bbox[0:2],
                                      self.test_cfg.exemplar_size, z_size,
                                      avg_channel)
        z_feat = self.forward_template(z_crop)
        return z_feat, avg_channel

    def track(self, img, bbox, z_feat, avg_channel):
        z_width = bbox[2] + self.test_cfg.context_amount * (bbox[2] + bbox[3])
        z_height = bbox[3] + self.test_cfg.context_amount * (bbox[2] + bbox[3])
        z_size = torch.sqrt(z_width * z_height)

        x_size = torch.round(
            z_size *
            (self.test_cfg.instance_size / self.test_cfg.exemplar_size))
        x_crop = self.get_cropped_img(img, bbox[0:2],
                                      self.test_cfg.instance_size, x_size,
                                      avg_channel)

        x_feat = self.forward_search(x_crop)
        cls_score, bbox_pred = self.head(z_feat, x_feat)
        scale_factor = self.test_cfg.exemplar_size / z_size
        best_score, best_bbox = self.head.get_bbox(cls_score, bbox_pred, bbox,
                                                   scale_factor)

        # clip boundary
        best_bbox = self._bbox_clip(best_bbox, img.shape[2], img.shape[3])
        return best_score, best_bbox

    def simple_test(self, img, img_metas, gt_bboxes, **kwargs):
        frame_id = img_metas[0].get('frame_id', -1)
        assert frame_id >= 0
        assert len(img) == 1, 'only support batch_size=1 when testing'

        if frame_id == 0:
            gt_bboxes = gt_bboxes[0]
            self.memo = Dict()
            self.memo.bbox = bbox_xyxy_to_cxcywh(gt_bboxes)
            self.memo.z_feat, self.memo.avg_channel = self.init(
                img, self.memo.bbox)
            best_score = None
        else:
            best_score, self.memo.bbox = self.track(img, self.memo.bbox,
                                                    self.memo.z_feat,
                                                    self.memo.avg_channel)

        bbox_pred = bbox_cxcywh_to_xyxy(self.memo.bbox)
        results = dict()
        if best_score is None:
            results['score'] = best_score
        else:
            results['score'] = best_score.cpu().numpy()
        results['bbox'] = bbox_pred.cpu().numpy()
        return results

    def forward_train(self, **kwargs):
        pass