#!/usr/bin/env python
# -*- coding: utf-8 -*-

from model import StackedAutoEncoder
from model import SummaryWriter

from inputlayer import OpenCVInputLayer

import tensorflow as tf

import numpy as np
import model.utils as utils
from os.path import join as pjoin

#utils.start_tensorboard()

print "recording summaries to " + SummaryWriter().directory

models = []

for _ in xrange(4):
    models.append(StackedAutoEncoder(
        dims=[100],
        activations=['linear'], 
        noise='gaussian', 
        epoch=[10],
        loss='rmse',
        lr=0.007
    ))

# Initialize input layer, register callback and feed video
inputlayer = OpenCVInputLayer(output_size=(32,32), batch_size=1)

inputlayer.registerCallback([00,00,16,16], models[0].fit)
inputlayer.registerCallback([16,00,16,16], models[1].fit)
inputlayer.registerCallback([00,16,16,16], models[2].fit)
inputlayer.registerCallback([16,16,16,16], models[3].fit)

inputlayer.feedVideo("data/hand.m4v", frames=20)

for model in models:
    model.write_activation_summary()