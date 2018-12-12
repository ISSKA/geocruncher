# -*- coding: utf-8 -*-

from .topography_reader import txt_extract
import sys
import re
import os
import numpy as np
from gmlib.GeologicalModel3D import GeologicalModel
from .ComputeIntersections import CrossSectionIntersections, MapIntersections, GeocruncherJsonEncoder
import json
from .MeshGeneration import generate_volumes
from pprint import pprint

def main():
    run_geocruncher(sys.argv)

def run_geocruncher(args):
    model = GeologicalModel(args[3])
    model.topography = txt_extract(args[4])
    box = model.getbox()

    if args[1] == 'all':
        with open(args[2]) as f:
            data = json.load(f)
        nPoints=40
        crossSections = []
        for rect in data:
            xCoord=[rect["lowerLeft"]["x"], rect["upperRight"]["x"]]
            yCoord=[rect["lowerLeft"]["y"], rect["upperRight"]["y"]]
            xCoordNew=[rect["lowerLeft"]["x"], rect["upperRight"]["x"]]
            yCoordNew=[rect["lowerLeft"]["y"], rect["upperRight"]["y"]]
            zCoord=[rect["lowerLeft"]["z"], rect["upperRight"]["z"]]
            if zCoord[0] < box.zmax or zCoord[0] > box.zmin or zCoord[1] > box.zmin or zCoord[1] < box.zmax:
                if isOutofBounds(xCoord[0], yCoord[0], box) == True:
                    (xCoordNew[0], yCoordNew[0]) = intersectBounds(xCoord, yCoord, zCoord, box, 0)
                if isOutofBounds(xCoord[1], yCoord[1], box) == True:
                    (xCoordNew[1], yCoordNew[1]) = intersectBounds(xCoord, yCoord, zCoord, box, 1)
            widthNew = np.sqrt(np.power(xCoordNew[0]-xCoordNew[1], 2) + np.power(yCoordNew[0]-yCoordNew[1], 2))
            width = np.sqrt(np.power(xCoord[0]-xCoord[1],2) + np.power(yCoord[0]-yCoord[1],2))
            ratio = widthNew / width
            offSet = np.sqrt(np.power(xCoord[0]-xCoordNew[0],2) + np.power(yCoord[0]-yCoordNew[0],2)) / width
            xCoord = xCoordNew
            yCoord = yCoordNew
            if xCoord[0] == xCoord[1]:
                xCoord[0] = xCoord[1] + 1
            crossSections.append( CrossSectionIntersections.output(xCoord,yCoord,zCoord,nPoints,model, [1, ratio], offSet));
        xCoord=[box.xmin,box.xmax]
        yCoord=[box.ymin,box.ymax]
        nPoints=60
        outputs = { 'forMaps': MapIntersections.output(xCoord,yCoord,nPoints,model), 'forCrossSections': crossSections }
        with open(args[5], 'w') as f:
            json.dump(outputs, f, indent = 2, cls=GeocruncherJsonEncoder)
        sys.stdout.flush()

    if args[1] == 'meshes':
        """
        Call: main.py meshes [num_samples] [geological_model_path] [surface_model_path] [out_dir]
        """
        num_samples = int(args[2])
        shape = (num_samples, num_samples, num_samples)
        out_dir = args[5]

        generated_mesh_paths = generate_volumes(model, shape, out_dir)
        # TODO do something useful with output files
        print(generated_mesh_paths)

    if args[1] == 'surface':
        nPoints=500
        data = json.loads(args[2])
        xCoord=np.array([data["start"]["x"], data["end"]["x"]])
        yCoord=np.array([data["start"]["y"], data["end"]["y"]])
        zCoord=np.array([data["minElevation"], data["maxElevation"]])  
        xCoordinds = xCoord.argsort()
        xCoord = xCoord[xCoordinds[::-1]]
        yCoord = yCoord[xCoordinds[::-1]]
        outputs = {'forSurface': CrossSectionSurface.output(xCoord,yCoord,zCoord,nPoints,model, [1, 1])} 
        (rank) = CrossSectionSurface.output(xCoord,yCoord,zCoord,nPoints,model, [1, 1])
        outputs = { 'rank': rank }
        #import codecs
        #json.dump(outputs,codecs.open('output.json', 'w', encoding='utf-8'), indent = 2, separators=(',', ': '))    
        with open(args[5], 'w') as f:
            json.dump(outputs, f, indent = 2, separators=(',', ': '))        
        sys.stdout.flush()

def isOutofBounds(xCoord, yCoord, box):
    if xCoord > box.xmax or xCoord < box.xmin or yCoord > box.ymax or yCoord < box.ymin:
        return True
    else :
        return False

def intersectBounds(xCoord, yCoord, zCoord, box, index):
    slope = (yCoord[1] - yCoord[0]) /  (xCoord[1] - xCoord[0])
    y0 = yCoord[0] - (xCoord[0] * slope)
    intersection_Points = np.array([])
    if box.ymin < box.xmin * slope + y0 and box.xmin * slope + y0 < box.ymax:
        intersection_Points = np.append(intersection_Points, [box.xmin, box.xmin * slope + y0])
    if box.ymin < box.xmax * slope + y0 and box.xmax * slope + y0 < box.ymax:
        intersection_Points = np.append(intersection_Points,[box.xmax, box.xmax * slope + y0])
    if box.xmin < (box.ymin - y0) / slope and (box.ymin - y0) / slope < box.xmax:
        intersection_Points = np.append(intersection_Points,[(box.ymin - y0) / slope, box.ymin])
    if box.xmin < (box.ymax - y0) / slope and (box.ymax - y0) / slope < box.xmax:
        intersection_Points = np.append(intersection_Points,[(box.ymax - y0) / slope, box.ymax])
    if np.size(intersection_Points) == 2:
	    return [intersection_Points[0]]
    if np.size(intersection_Points) == 4:
        if np.linalg.norm(np.array([intersection_Points[0],intersection_Points[1]]) - np.array([xCoord[index], yCoord[index]])) < np.linalg.norm(np.array([intersection_Points[2],intersection_Points[3]])- np.array([xCoord[index], yCoord[index]])):
	        return [intersection_Points[0],intersection_Points[1]]
        else:
	        return [intersection_Points[2],intersection_Points[3]]
    if np.size(intersection_Points) == 0:
        return [0,0]
