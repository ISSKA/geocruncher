# -*- coding: utf-8 -*-

import argparse
from pathlib import Path
import json
import sys
import os
from gmlib.GeologicalModel3D import GeologicalModel
from gmlib.GeologicalModel3D import Box

from .ComputeIntersections import MapFaultIntersection, Slice, MapSlice, FaultIntersection
from .MeshGeneration import generate_volumes, generate_faults
from .topography_reader import txt_extract
from .tunnel_shape_generation import get_circle_segment, get_elliptic_segment, get_rectangle_segment, tunnel_to_meshes
from .voxel_computation import _compute_voxels

from .profiler.profiler import VkProfiler, PROFILES, set_current_profiler, get_current_profiler, set_is_profiling_enabled, set_profiler_output_folder
from .profiler.util import MetadataHelpers


RATIO_MAX_DIST_PROJ = 0.2


def main():
    # TODO: WIP argument parsing
    # Currently, flag arguments need to be passed last, because Geocruncher requires specific parameters at specific indices in the argument list
    # It would be interresting to convert everything to argparse, to make it more robust, and take advantage of the error handling / help messages
    parser = argparse.ArgumentParser(
        prog='Geocruncher',
        description='A small wrapper for the gmlib library. Intended as a stand-alone executable reading input data from files.',
        epilog='Stable command line arguments are still WIP. Currently, flag arguments must be passed last, and not everything is documented above.'
    )
    parser.add_argument('computation', choices=[
                        'tunnel_meshes', 'meshes', 'intersections', 'faults', 'faults_intersections', 'voxels'], help='the type of computation to perform')
    parser.add_argument('--enable-profiling',
                        action='store_true', help='enable profiling for this computation (default: disabled)')
    parser.add_argument('--profiler-output', type=Path,
                        help='custom folder for the output of the profiler (default: working directory)', default=Path.cwd())
    p = parser.parse_known_args()[0]

    if not p.profiler_output.exists() or not p.profiler_output.is_dir():
        parser.error("Profiler output either doesn't exist or isn't a folder")

    set_is_profiling_enabled(p.enable_profiling)
    set_profiler_output_folder(p.profiler_output)

    run_geocruncher(p.computation, sys.argv)


def run_geocruncher(computation: str, args: list[str]):
    if computation == 'tunnel_meshes':
        with open(args[2]) as f:
            data = json.load(f)
        # sub tunnel are a bit bigger to wrap main tunnel
        subT = 1.10 if data["idxStart"] != -1 and data["idxEnd"] != -1 else 1.0
        plane_segment = {
            "Circle": lambda t: get_circle_segment(t["radius"] * subT, data["nb_vertices"]),
            "Rectangle": lambda t: get_rectangle_segment(t["width"] * subT, t["height"] * subT, data["nb_vertices"]),
            "Elliptic": lambda t: get_elliptic_segment(t["width"] * subT, t["height"] * subT, data["nb_vertices"])
        }
        for tunnel in data["tunnels"]:
            # profile each tunnel separatly
            set_current_profiler(VkProfiler(PROFILES[computation]))
            get_current_profiler()\
                .set_profiler_metadata('shape', tunnel["shape"])\
                .set_profiler_metadata('num_waypoints', len(tunnel["functions"]) + 1)
            tunnel_to_meshes(tunnel["functions"], data["step"], plane_segment[tunnel["shape"]](
                tunnel), data["idxStart"], data["tStart"], data["idxEnd"], data["tEnd"], os.path.join(args[3], tunnel["name"] + ".off"))
            # write profiler result before moving on to the next tunnel
            get_current_profiler().save_profiler_results()

        return

    set_current_profiler(VkProfiler(PROFILES[computation]))

    model = GeologicalModel(args[3])
    model.topography = txt_extract(args[4])
    box = model.getbox()

    if computation == 'meshes':
        """
        Call: main.py meshes [configuration_path] [geological_model_path] [surface_model_path] [out_dir]
        """
        with open(args[2]) as f:
            data = json.load(f)
        shape = (int(data["resolution"]["x"]), int(
            data["resolution"]["y"]), int(data["resolution"]["z"]))
        out_dir = args[5]

        get_current_profiler()\
            .set_profiler_metadata('num_series', MetadataHelpers.num_series(model))\
            .set_profiler_metadata('num_units', MetadataHelpers.num_units(model))\
            .set_profiler_metadata('num_finite_faults', MetadataHelpers.num_finite_faults(model))\
            .set_profiler_metadata('num_infinite_faults', MetadataHelpers.num_infinite_faults(model))\
            .set_profiler_metadata('num_interfaces', MetadataHelpers.num_interfaces(model))\
            .set_profiler_metadata('num_foliations', MetadataHelpers.num_foliations(model))\
            .set_profiler_metadata('resolution', shape[0] * shape[1] * shape[2])\
            .profile('load_model')

        if "box" in data and data["box"]:
            optBox = Box(xmin=float(data["box"]["xMin"]),
                         ymin=float(data["box"]["yMin"]),
                         zmin=float(data["box"]["zMin"]),
                         xmax=float(data["box"]["xMax"]),
                         ymax=float(data["box"]["yMax"]),
                         zmax=float(data["box"]["zMax"]))
            generated_mesh_paths = generate_volumes(
                model, shape, out_dir, optBox)
        else:
            generated_mesh_paths = generate_volumes(model, shape, out_dir, box)

    if computation == 'intersections':
        crossSections, drillholesLines, springsPoint, matrixGwb = {}, {}, {}, {}

        meshes_files = []
        with open(args[2]) as f:
            data = json.load(f)
        if "springs" in data or "drillholes" in data:
            meshes_files = [args[5] + "/" +
                            f for f in os.listdir(args[5]) if f.endswith(".off")]

        nPoints = data["resolution"]

        get_current_profiler()\
            .set_profiler_metadata('num_series', MetadataHelpers.num_series(model))\
            .set_profiler_metadata('num_units', MetadataHelpers.num_units(model))\
            .set_profiler_metadata('num_interfaces', MetadataHelpers.num_interfaces(model, fault=False))\
            .set_profiler_metadata('num_foliations', MetadataHelpers.num_foliations(model, fault=False))\
            .set_profiler_metadata('resolution', nPoints)\
            .set_profiler_metadata('num_sections', len(data["toCompute"].items()))\
            .set_profiler_metadata('compute_map', data["computeMap"])\
            .set_profiler_metadata('num_springs', len(data["springs"]) if data["springs"] else 0)\
            .set_profiler_metadata('num_drillholes', len(data["drillholes"]) if data["drillholes"] else 0)\
            .set_profiler_metadata('num_gwb_parts', len(meshes_files))\
            .profile('load_model')

        for sectionId, rect in data["toCompute"].items():
            xCoord = [int(round(rect["lowerLeft"]["x"])),
                      int(round(rect["upperRight"]["x"]))]
            yCoord = [int(round(rect["lowerLeft"]["y"])),
                      int(round(rect["upperRight"]["y"]))]
            zCoord = [int(round(rect["lowerLeft"]["z"])),
                      int(round(rect["upperRight"]["z"]))]
            maxDistProj = max(box.xmax - box.xmin, box.ymax -
                              box.ymin) * RATIO_MAX_DIST_PROJ
            key = str(sectionId)
            crossSections[key], drillholesLines[key], springsPoint[key], matrixGwb[key] = Slice.output(
                xCoord, yCoord, zCoord, nPoints, model.rank, [1, 1], model.pile.reference == "base", data, meshes_files, maxDistProj)

        outputs = {'forCrossSections': crossSections, 'drillholes': drillholesLines,
                   "springs": springsPoint, "matrixGwb": matrixGwb}
        if data["computeMap"]:
            xCoord = [box.xmin, box.xmax]
            yCoord = [box.ymin, box.ymax]
            outputs['forMaps'] = MapSlice.output(
                xCoord, yCoord, nPoints, model.rank, model.topography.evaluate_z, model.pile.reference == "base")

        with open(args[6], 'w') as f:
            json.dump(outputs, f, indent=2, separators=(',', ': '))
        sys.stdout.flush()
        get_current_profiler().profile('write_output')

    if computation == "faults":
        with open(args[2]) as f:
            data = json.load(f)
        shape = (data["resolution"]["x"], data["resolution"]
                 ["y"], data["resolution"]["z"])
        out_dir = args[5]

        get_current_profiler()\
            .set_profiler_metadata('num_finite_faults', MetadataHelpers.num_finite_faults(model))\
            .set_profiler_metadata('num_infinite_faults', MetadataHelpers.num_infinite_faults(model))\
            .set_profiler_metadata('num_interfaces', MetadataHelpers.num_interfaces(model, unit=False))\
            .set_profiler_metadata('num_foliations', MetadataHelpers.num_foliations(model, unit=False))\
            .set_profiler_metadata('resolution', shape[0] * shape[1] * shape[2])\
            .profile('load_model')

        generated_mesh_paths = generate_faults(model, shape, out_dir)

    if computation == "faults_intersections":
        outputs = {}
        with open(args[2]) as f:
            data = json.load(f)

        nPoints = data["resolution"]

        get_current_profiler()\
            .set_profiler_metadata('num_finite_faults', MetadataHelpers.num_finite_faults(model))\
            .set_profiler_metadata('num_infinite_faults', MetadataHelpers.num_infinite_faults(model))\
            .set_profiler_metadata('num_interfaces', MetadataHelpers.num_interfaces(model, unit=False))\
            .set_profiler_metadata('num_foliations', MetadataHelpers.num_foliations(model, unit=False))\
            .set_profiler_metadata('resolution', nPoints)\
            .set_profiler_metadata('num_sections', len(data["toCompute"].items()))\
            .set_profiler_metadata('compute_map', data["computeMap"])\
            .profile('load_model')

        for sectionId, rect in data["toCompute"].items():
            xCoord = [int(round(rect["lowerLeft"]["x"])),
                      int(round(rect["upperRight"]["x"]))]
            yCoord = [int(round(rect["lowerLeft"]["y"])),
                      int(round(rect["upperRight"]["y"]))]
            zCoord = [int(round(rect["lowerLeft"]["z"])),
                      int(round(rect["upperRight"]["z"]))]
            outputs[str(sectionId)] = FaultIntersection.output(
                xCoord, yCoord, zCoord, nPoints, model)
        outputs = {'forCrossSections': outputs}
        if data["computeMap"]:
            xCoord = [box.xmin, box.xmax]
            yCoord = [box.ymin, box.ymax]
            outputs['forMaps'] = MapFaultIntersection.output(
                xCoord, yCoord, nPoints, model)

        with open(args[5], 'w') as f:
            json.dump(outputs, f, indent=2, separators=(',', ': '))
        sys.stdout.flush()
        get_current_profiler().profile('write_output')

    if computation == "voxels":
        with open(args[2]) as f:
            data = json.load(f)
        shape = (int(data["resolution"]["x"]), int(
            data["resolution"]["y"]), int(data["resolution"]["z"]))
        out_file = args[6]
        box = Box(xmin=float(data["box"]["xMin"]),
                  ymin=float(data["box"]["yMin"]),
                  zmin=float(data["box"]["zMin"]),
                  xmax=float(data["box"]["xMax"]),
                  ymax=float(data["box"]["yMax"]),
                  zmax=float(data["box"]["zMax"]))
        meshes_files = [args[5] + "/" +
                        f for f in os.listdir(args[5]) if f.endswith(".off")]

        get_current_profiler()\
            .set_profiler_metadata('num_series', MetadataHelpers.num_series(model))\
            .set_profiler_metadata('num_units', MetadataHelpers.num_units(model))\
            .set_profiler_metadata('num_gwb_parts', len(meshes_files))\
            .set_profiler_metadata('resolution', shape[0] * shape[1] * shape[2])\
            .profile('load_model')

        _compute_voxels(shape, box, model, meshes_files, out_file)

    get_current_profiler().save_profiler_results()
