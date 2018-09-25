# -*- coding: utf-8 -*-
#
# This file is part of gmlib. It is free software.
# You can redistribute it and/or modify it under the terms of the GNU Affero General Public License version 3.
#

import os
import numpy as np
import re

def txt_extract(file):
    # Original code uses file, but for minimum changing we use StringIO
    
    f = open(file)#Modified
    ncols =float(re.findall(r"\d+",f.readline())[0])
    nrows =float(re.findall(r"\d+",f.readline())[0])
    xllcorner =float(re.findall(r"-?\d+\.\d+",f.readline())[0])
    yllcorner =float(re.findall(r"-?\d+\.\d+",f.readline())[0])
    cellsize =float(re.findall(r"-?\d+\.\d+",f.readline())[0])
    f.readline()
    zmap = []
    line = f.readline().strip().split()
    while line:
        reversed_arr = np.array([float(s) for s in line])
        zmap.append(reversed_arr)
        line = f.readline().strip().split()
    zmap = np.array(zmap[::-1])
    xRange=np.linspace(xllcorner,xllcorner+cellsize*(ncols),ncols+1)
    yRange=np.linspace(yllcorner,yllcorner+cellsize*(nrows),nrows+1)


    return ImplicitDTM((xllcorner, yllcorner), (float(cellsize), float(cellsize)), zmap.transpose())
