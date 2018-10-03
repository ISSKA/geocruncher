# -*- coding: utf-8 -*-

from . import topography_reader
from .geomodeller_project import extract_project_data_noTopography
import sys
import re
import os
import numpy as np
from .GeologicalModel3D import GeologicalModel
from .ComputeIntersections import CrossSectionIntersections, MapIntersections
import json
from pprint import pprint


if __name__ == '__main__':
	
    #[box, pile, faults_data]=extract_project_data_noTopography(sys.argv[3])
    model = GeologicalModel(sys.argv[3],sys.argv[4])
    box = model.getbox()
    

    if sys.argv[1] == 'crossSection':
        with open(sys.argv[2]) as f:
            data = json.load(f)
        nPoints=60
        xCoord=[data["lowerLeft"]["x"],data["upperRight"]["x"]]
        yCoord=[data["lowerLeft"]["y"],data["upperRight"]["y"]]
        zCoord=[data["lowerLeft"]["z"],data["upperRight"]["z"]]
        imgSize=[10000,10000]#hardcoded for now   
        (outputX, outputY, outputRank) = CrossSectionIntersections.output(xCoord,yCoord,zCoord,nPoints,model,imgSize);
        output = "{\"X\":%(outputX)s ,\"Y\":%(outputY)s ,\"serieBelow\":%(outputRank)s}" % locals() #for optimisation
        sys.stdout.write(output)
        sys.stdout.flush()
    
    if sys.argv[1] == "map":
        nPoints=80
        xCoord=[box.xmin,box.xmax]
        yCoord=[box.ymin,box.ymax]
        (outputX, outputY, outputRank) = MapIntersections.output(xCoord,yCoord,nPoints,model)
        output = "{\"X\":%(outputX)s ,\"Y\":%(outputY)s ,\"serieBelow\":%(outputRank)s}" % locals() #for optimisation
        sys.stdout.write(output)
        sys.stdout.flush()
    
    if sys.argv[1] == 'all':
        with open(sys.argv[2]) as f:
            data = json.load(f)
        nPoints=30
        numberfromstring=re.findall(r"-?\d+\.\d+",sys.argv[2])
        output="{"
        i=0
        for i in range(0, len(data)):
            xCoord=[data[i]["lowerLeft"]["x"],data[i]["upperRight"]["x"]]
            yCoord=[data[i]["lowerLeft"]["y"],data[i]["upperRight"]["y"]]
            zCoord=[data[i]["lowerLeft"]["z"],data[i]["upperRight"]["z"]]
            imgSize=[10000,10000]#hardcoded for now          
            (outputX, outputY, outputRank)=CrossSectionIntersections.output(xCoord,yCoord,zCoord,nPoints,model,imgSize);
            index=str(i)
            i=i+1
            output = "%(output)s\"CrossSection%(index)s\":{\"X\":%(outputX)s ,\"Y\":%(outputY)s ,\"serieBelow\":%(outputRank)s}," % locals()
        xCoord=[box.xmin,box.xmax]
        yCoord=[box.ymin,box.ymax]
        nPoints=45
        (outputX, outputY, outputRank)=MapIntersections.output(xCoord,yCoord,nPoints,model)
        output = "%(output)s\"Map\":{\"X\":%(outputX)s ,\"Y\":%(outputY)s ,\"serieBelow\":%(outputRank)s}}" % locals() #for optimisation
        sys.stdout.write(output)
        sys.stdout.flush()
    
