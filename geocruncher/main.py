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
        nPoints=30
        crossSections = []
        for rect in data:
            xCoord=[rect["lowerLeft"]["x"], rect["upperRight"]["x"]]
            yCoord=[rect["lowerLeft"]["y"], rect["upperRight"]["y"]]
            zCoord=[rect["lowerLeft"]["z"], rect["upperRight"]["z"]]
            crossSections.append(CrossSectionIntersections.output(xCoord,yCoord,zCoord,nPoints,model, [1, 1]));
        xCoord=[box.xmin,box.xmax]
        yCoord=[box.ymin,box.ymax]
        nPoints=45
        outputs = { 'forMaps': MapIntersections.output(xCoord,yCoord,nPoints,model), 'forCrossSections': crossSections }
        with open(args[5], 'w') as f:
            json.dump(outputs, f, indent = 2, cls=GeocruncherJsonEncoder)
        sys.stdout.flush()

    if args[1] == 'meshes':
        """
        Call: main.py meshes [num_samples] [geological_model_path] [surface_model_path] [out_dir]
        """
        num_samples = int(args[2])
        shape = tuple(num_samples, num_samples, num_samples)
        out_dir = args[5]

        generated_mesh_paths = generate_volumes(model, shape, out_dir)
        # TODO do something useful with output files
        print(generated_mesh_paths)