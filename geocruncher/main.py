# -*- coding: utf-8 -*-


from . import topography_reader
from .geomodeller_project import extract_project_data_noTopography
import sys
import re
import os
import numpy as np
from .GeologicalModel3D import GeologicalModel
from .ComputeIntersections import CrossSectionIntersections, MapIntersections, GeocruncherJsonEncoder
import json
from pprint import pprint



def main():
    run_geocruncher(sys.argv)

def run_geocruncher(args):

    #[box, pile, faults_data]=extract_project_data_noTopography(sys.argv[3])
    model = GeologicalModel(args[3], args[4])
    box = model.getbox()
    

    if args[1] == 'crossSection':
        with open(sys.args[2]) as f:
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
    
    if args[1] == "map":
        nPoints=80
        xCoord=[box.xmin,box.xmax]
        yCoord=[box.ymin,box.ymax]
        (outputX, outputY, outputRank) = MapIntersections.output(xCoord,yCoord,nPoints,model)
        output = "{\"X\":%(outputX)s ,\"Y\":%(outputY)s ,\"serieBelow\":%(outputRank)s}" % locals() #for optimisation
        sys.stdout.write(output)
        sys.stdout.flush()
    
    if args[1] == 'all':
        with open(args[2]) as f:
            data = json.load(f)
        nPoints=30
        crossSections = []
        for rect in data:
            xCoord=[rect["lowerLeft"]["x"], rect["upperRight"]["x"]]
            yCoord=[rect["lowerLeft"]["y"], rect["upperRight"]["y"]]
            zCoord=[rect["lowerLeft"]["z"], rect["upperRight"]["z"]]
            imgSize=[10000,10000]#hardcoded for now
            crossSections.append(CrossSectionIntersections.output(xCoord,yCoord,zCoord,nPoints,model,imgSize));
        xCoord=[box.xmin,box.xmax]
        yCoord=[box.ymin,box.ymax]
        nPoints=45
        outputs = { 'forMaps': MapIntersections.output(xCoord,yCoord,nPoints,model), 'forCrossSections': crossSections }
        with open(args[5], 'w') as f:
            json.dump(outputs, f, indent = 2, cls=GeocruncherJsonEncoder)
        sys.stdout.flush()
    
