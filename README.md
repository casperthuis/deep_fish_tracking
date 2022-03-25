# Fish tracking lib for tracking fish in moving camera setup.

This repo is a fish tracking lib on top of mmtracking lib to track fishes in moving camera setup. The lib contain the possibility to train/evaluated and demo vids of predator prey interaction. The general purpose of this repo is to create a working tracking solution and to create some functionalities on top of that such as a GUI to load videos, process frames, correct tracking behaviour and save tracks.

## Project status 
**Work in progress.**


# Visuals

![Predator](gifs/predator.gif)
![Prey](gifs/prey.gif)

# Installation

To install this repo on can simply clone or fork it and following the instructions for installing mmtracking repo [Here](https://github.com/open-mmlab/mmtracking/blob/master/docs/en/install.md)

# Usage

To start tracking in one of the video's one would one of the following criteria. 

- Installing mmtrackig
- Download a checkpoint file or train a model
- Define a config
- run demo_sot.py in the demo folder with the following commands.
```
VID_PATH="LOCATION OF YOUR VIDEO FILE"
CHECKPOINT_PATH="LOCATION OF YOUR CHECKPOINT FILE"
CONFIG_PATH="LOCATION OF YOUR CONFIG FILE"
python ./demo/demo_sot.py \                                            
    ${CONFIG_PATH} \
    --input ${VID_PATH} \
    --checkpoint ${CONFIG_PATH} \ 
--show 
```

Select a box around the object by clicking and pressing enter.


# Roadmap
- [] Make data available
- [] GUI creation for loss of tracking object
- [] Create center evaluation metric for evaluation
- [] Adapt data scheme to current format
- [] Test mot solutions for moorea dataset
- [] Create detection model for moorea dataset


# Authors and acknowledgment
Casper Thuis -> name.name@gmail.com  

We made use of the functionality of mmtracking framework 
```
@misc{mmtrack2020,
    title={{MMTracking: OpenMMLab} video perception toolbox and benchmark},
    author={MMTracking Contributors},
    howpublished = {\url{https://github.com/open-mmlab/mmtracking}},
    year={2020}
}
```

# License

