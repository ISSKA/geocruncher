# -*- coding: utf-8 -*-

import json
import numpy as np
import sys
import os
from gmlib.GeologicalModel3D import GeologicalModel
from gmlib.GeologicalModel3D import Box

from geocruncher.ComputeIntersections import Slice, MapSlice, FaultIntersection
from geocruncher.MeshGeneration import generate_volumes, generate_faults
from geocruncher.topography_reader import txt_extract
from geocruncher.TunnelFunctions import computeBezierCoefficients, computeArcLength


def main():
    run_geocruncher(sys.argv)


def run_geocruncher(args):
    if args[1] != "bezier_interpolation" and args[1] != "arc_length" and len(args) > 4 and os.path.exists(args[3]) and os.path.exists(args[4]):
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


    if args[1] == "faults_intersections":
        outputs = {}
        with open(args[2]) as f:
            data = json.load(f)
        nPoints = data["resolution"]
        for sectionId, rect in data["toCompute"].items():
            xCoord = [int(round(rect["lowerLeft"]["x"])), int(round(rect["upperRight"]["x"]))]
            yCoord = [int(round(rect["lowerLeft"]["y"])), int(round(rect["upperRight"]["y"]))]
            zCoord = [int(round(rect["lowerLeft"]["z"])), int(round(rect["upperRight"]["z"]))]
            outputs[str(sectionId)] = FaultIntersection.output(xCoord, yCoord, zCoord, nPoints, model)
        outputs = {'values': outputs}

        with open(args[5], 'w') as f:
            json.dump(outputs, f, indent=2, separators=(',', ': '))
        sys.stdout.flush()

    if args[1] == "bezier_interpolation":
        with open(args[2]) as f:
            data = json.load(f)
        points = np.array([[p["x"], p["y"], p["z"]] for p in data["points"]])
        A, B = computeBezierCoefficients(points)
        output = {}
        output["A"] = A.tolist()
        output["B"] = [b.tolist() for b in B]

        with open(args[3], 'w') as f:
            json.dump(output, f, indent=2, separators=(',', ': '))
        sys.stdout.flush()

    if args[1] == "arc_length":
        with open(args[2]) as f:
            data = json.load(f)
        output = {"results": []}
        for f in data["functions"]:
            output["results"].append(computeArcLength(f["function"], f["start"], f["end"]))
            
        with open(args[3], 'w') as f:
            json.dump(output, f, indent=2, separators=(',', ': '))
        sys.stdout.flush()

