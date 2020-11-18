# -*- coding: utf-8 -*-

import json
import numpy as np
import sys
from gmlib.GeologicalModel3D import GeologicalModel
from gmlib.GeologicalModel3D import Box

from .ComputeIntersections import Slice, MapSlice
from .MeshGeneration import generate_volumes, generate_faults
from .topography_reader import txt_extract


def main():
    run_geocruncher(sys.argv)


def run_geocruncher(args):
    model = GeologicalModel(args[3])
    model.topography = txt_extract(args[4])
    box = model.getbox()

    if args[1] == 'meshes':
        """
        Call: main.py meshes [configuration_path] [geological_model_path] [surface_model_path] [out_dir]
        """
        # num_samples = int(args[2])
        with open(args[2]) as f:
            data = json.load(f)
        shape = (int(data["resolution"]["x"]), int(data["resolution"]["y"]), int(data["resolution"]["z"]))
        out_dir = args[5]

        if "box" in data and data["box"]:
            optBox = Box(xmin=float(data["box"]["xMin"]), 
                ymin=float(data["box"]["yMin"]), 
                zmin=float(data["box"]["zMin"]), 
                xmax=float(data["box"]["xMax"]), 
                ymax=float(data["box"]["yMax"]), 
                zmax=float(data["box"]["zMax"]))
            generated_mesh_paths = generate_volumes(model, shape, out_dir, optBox)
        else:
            generated_mesh_paths = generate_volumes(model, shape, out_dir)
        # TODO do something useful with output files
        print(generated_mesh_paths)

    if args[1] == 'slice':
        nPoints = 300
        slices = []
        with open(args[2]) as f:
            data = json.load(f)
        for rect in data:
            xCoord = [int(round(rect["lowerLeft"]["x"])), int(round(rect["upperRight"]["x"]))]
            yCoord = [int(round(rect["lowerLeft"]["y"])), int(round(rect["upperRight"]["y"]))]
            zCoord = [int(round(rect["lowerLeft"]["z"])), int(round(rect["upperRight"]["z"]))]
            slices.append({'values': Slice.output(xCoord, yCoord, zCoord, nPoints, model.rank, [1, 1])})
        outputs = {'slices': slices}
        with open(args[5], 'w') as f:
            json.dump(outputs, f, indent=2, separators=(',', ': '))
        sys.stdout.flush()

    if args[1] == 'intersections':
        crossSections = {}
        with open(args[2]) as f:
            data = json.load(f)
        nPoints = data["resolution"]
        for sectionId, rect in data["toCompute"].items():
            xCoord = [int(round(rect["lowerLeft"]["x"])), int(round(rect["upperRight"]["x"]))]
            yCoord = [int(round(rect["lowerLeft"]["y"])), int(round(rect["upperRight"]["y"]))]
            zCoord = [int(round(rect["lowerLeft"]["z"])), int(round(rect["upperRight"]["z"]))]
            crossSections[str(sectionId)] = Slice.output(xCoord, yCoord, zCoord, nPoints, model.rank, [1, 1])
        outputs = {'forCrossSections': crossSections}
        if data["computeMap"]:
          xCoord = [box.xmin, box.xmax]
          yCoord = [box.ymin, box.ymax]
          outputs['forMaps'] = MapSlice.output(xCoord, yCoord, nPoints, model.rank, model.topography.evaluate_z)
        with open(args[5], 'w') as f:
            json.dump(outputs, f, indent=2, separators=(',', ': '))
        sys.stdout.flush()

    if args[1] == "faults":
        with open(args[2]) as f:
            data = json.load(f)
        shape = (data["resolution"]["x"], data["resolution"]["y"], data["resolution"]["z"])
        out_dir = args[5]

        generated_mesh_paths = generate_faults(model, shape, out_dir)
