# -*- coding: utf-8 -*-

import topography_reader
from geomodeller_project import extract_project_data_noTopography
import sys
import re
import os
import numpy as np
from GeologicalModel3D import GeologicalModel
from ComputeIntersections import CrossSectionIntersections
from ComputeIntersections import MapIntersections


if __name__ == '__main__':
	
    #[box, pile, faults_data]=extract_project_data_noTopography(sys.argv[3])
    model = GeologicalModel(sys.argv[3],sys.argv[4])
    box = model.getbox()

    if sys.argv[1] == 'crossSection':
        nPoints=60
        numberfromstring=re.findall(r"-?\d+\.\d+",sys.argv[2])
        xCoord=[float(numberfromstring[0]),float(numberfromstring[1])]
        yCoord=[float(numberfromstring[2]),float(numberfromstring[3])]
        zCoord=[float(numberfromstring[4]),float(numberfromstring[5])]
        imgSize=[float(numberfromstring[6]),float(numberfromstring[7])]          
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
        nPoints=30
        numberfromstring=re.findall(r"-?\d+\.\d+",sys.argv[2])
        output="{"
        sectionNumber=int(np.shape(numberfromstring)[0]/8)
        for i in range(0, sectionNumber):
            xCoord=[float(numberfromstring[0+i*8]),float(numberfromstring[1+i*8])]
            yCoord=[float(numberfromstring[2+i*8]),float(numberfromstring[3+i*8])]
            zCoord=[float(numberfromstring[4+i*8]),float(numberfromstring[5+i*8])]
            imgSize=[float(numberfromstring[6+i*8]),float(numberfromstring[7+i*8])]          
            (outputX, outputY, outputRank)=CrossSectionIntersections.output(xCoord,yCoord,zCoord,nPoints,model,imgSize);
            index=str(i)
            output = "%(output)s\"CrossSection%(index)s\":{\"X\":%(outputX)s ,\"Y\":%(outputY)s ,\"serieBelow\":%(outputRank)s}," % locals()
        xCoord=[box.xmin,box.xmax]
        yCoord=[box.ymin,box.ymax]
        nPoints=45
        (outputX, outputY, outputRank)=MapIntersections.output(xCoord,yCoord,nPoints,model)
        output = "%(output)s\"Map\":{\"X\":%(outputX)s ,\"Y\":%(outputY)s ,\"serieBelow\":%(outputRank)s}}" % locals() #for optimisation
        sys.stdout.write(output)
        sys.stdout.flush()
    
