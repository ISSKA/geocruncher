# -*- coding: utf-8 -*-

import json
import numpy as np
import sys
import os
from gmlib.GeologicalModel3D import GeologicalModel
from gmlib.GeologicalModel3D import Box

from .ComputeIntersections import MapFaultIntersection, Slice, MapSlice, FaultIntersection
from .MeshGeneration import generate_volumes, generate_faults
from .topography_reader import txt_extract
from .tunnel_shape_generation import get_circle_segment, get_elliptic_segment, get_rectangle_segment, tunnel_to_meshes

def main():
    run_geocruncher(sys.argv)


def run_geocruncher(args):
    if args[1] == 'tunnel_meshes':
        with open(args[2]) as f:
            data = json.load(f)
        plane_segment = {
            "Circle": lambda t: get_circle_segment(t["radius"], data["nb_vertices"]),
            "Rectangle": lambda t: get_rectangle_segment(t["width"], t["height"], data["nb_vertices"]),
            "Elliptic": lambda t: get_elliptic_segment(t["width"], t["height"], data["nb_vertices"])
        }
        for tunnel in data["tunnels"]:
            tunnel_to_meshes(tunnel["functions"], data["step"], plane_segment[tunnel["shape"]](tunnel), os.path.join(args[3], tunnel["name"] + ".off"))

        return

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
        outputs = {'forCrossSections': outputs}
        if data["computeMap"]:
            xCoord = [box.xmin, box.xmax]
            yCoord = [box.ymin, box.ymax]
            outputs['forMaps'] = MapFaultIntersection.output(xCoord, yCoord, nPoints, model)

        with open(args[5], 'w') as f:
            json.dump(outputs, f, indent=2, separators=(',', ': '))
        sys.stdout.flush()


