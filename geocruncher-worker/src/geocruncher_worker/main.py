# -*- coding: utf-8 -*-

import argparse
from pathlib import Path
import json
import sys
import os
from collections import defaultdict

from geocruncher_worker.computations import compute_tunnel_meshes, compute_meshes, compute_intersections, compute_faults, compute_voxels


def main():
    # TODO: WIP argument parsing
    # Currently, flag arguments need to be passed last, because Geocruncher requires specific parameters at specific indices in the argument list
    # It would be interresting to convert everything to argparse, to make it more robust, and take advantage of the error handling / help messages
    parser = argparse.ArgumentParser(
        prog='Geocruncher',
        description="Computation package mostly using BRGM technologies. It can be used both" \
        "as a standalone executable reading inputs from files and writing outputs to files, or as a python module." \
        "Profiling can be enabled and configured using environment variables. See the ProfilerConfig class.",
        epilog="Stable command line arguments are still WIP. Currently, flag arguments must be passed last, and not everything is documented above."
    )
    parser.add_argument('computation', choices=[
                        'tunnel_meshes', 'meshes', 'intersections', 'faults', 'voxels'], help="the type of computation to perform")

    p = parser.parse_known_args()[0]

    if not p.profiler_output.exists() or not p.profiler_output.is_dir():
        parser.error("Profiler output either doesn't exist or isn't a folder")

    run_geocruncher(p.computation, sys.argv)


def run_geocruncher(computation: str, args: list[str]):
    if computation == 'tunnel_meshes':
        # Call: main.py tunnel_meshes [configuration_path] [out_dir]
        with open(args[2], encoding='utf8') as f:
            data = json.load(f)
        meshes = compute_tunnel_meshes(data)
        for key, value in meshes.items():
            with open(os.path.join(args[3], key + '.off'), 'wb') as f:
                f.write(value)
        # with open(f'{args[3]}/mesh_tunnel_outputs_cli.json', 'w') as f:
        #     json.dump(meshes, f, indent=2)
        return

    if computation == 'meshes':
        # Call: main.py meshes [configuration_path] [geological_model_path] [surface_model_path] [out_dir]
        with open(args[2], encoding='utf8') as f:
            data = json.load(f)
        with open(args[3], 'rb') as f:
            xml = f.read()
        with open(args[4], 'r', encoding='utf8') as f:
            dem = f.read()
        out_dir = args[5]
        generated_meshes = compute_meshes(data, xml, dem)
        # TODO: used lists for compatibility, but they are useless as they always contain 1 item
        generated_meshes_paths = {'mesh': defaultdict(
            list), 'fault': defaultdict(list)}

        # write unit files
        for rank, off_mesh in generated_meshes['mesh'].items():
            filename = f"rank_{rank}.off"
            full_path = os.path.join(out_dir, filename)
            with open(full_path, 'wb') as f:
                f.write(off_mesh)
            generated_meshes_paths['mesh'][rank].append(full_path)

        # write fault files
        for name, off_mesh in generated_meshes['fault'].items():
            filename = f"fault_{name}.off"
            full_path = os.path.join(out_dir, filename)
            with open(full_path, 'wb') as f:
                f.write(off_mesh)
            generated_meshes_paths['fault'][name].append(full_path)

        # write meta json
        with open(os.path.join(out_dir, 'index.json'), 'w', encoding='utf8') as f:
            json.dump(generated_meshes_paths, f, indent=2)

    if computation == 'intersections':
        # Call: main.py intersections [configuration_path] [geological_model_path] [surface_model_path] [meshes_folder] [out_file]
        # Inside meshes_folder, GWB meshes have the following syntax: f"mesh_{id}_{subID}.off"
        with open(args[2], encoding='utf8') as f:
            data = json.load(f)
        with open(args[3], 'rb') as f:
            xml = f.read()
        with open(args[4], 'r', encoding='utf8') as f:
            dem = f.read()
        gwb_meshes = defaultdict(list)
        if 'springs' in data or 'drillholes' in data:
            for fp in os.listdir(args[5]):
                if not fp.endswith('.off'):
                    continue
                gwb_id = fp.split('_')[1]  # Syntax: f"mesh_{id}_{subID}.off"
                full_path = Path(args[5]).joinpath(fp)
                with open(full_path, encoding='utf8') as f:
                    gwb_meshes[gwb_id].append(f.read())
            # with open(args[5], encoding='utf8') as f:
            #     gwb_meshes = json.load(f)

        outputs = compute_intersections(data, xml, dem, gwb_meshes)

        with open(args[6], 'w', encoding='utf8') as f:
            json.dump(outputs, f, indent=2, separators=(',', ': '))
        sys.stdout.flush()

    if computation == 'faults':
        # Call: main.py faults [configuration_path] [geological_model_path] [surface_model_path] [out_dir]
        with open(args[2], encoding='utf8') as f:
            data = json.load(f)
        with open(args[3], 'rb') as f:
            xml = f.read()
        with open(args[4], 'r', encoding='utf8') as f:
            dem = f.read()
        out_dir = args[5]
        generated_meshes = compute_faults(data, xml, dem)
        # TODO: used lists for compatibility, but they are useless as they always contain 1 item
        generated_meshes_paths = {'mesh': {}, 'fault': defaultdict(list)}

        # write fault files
        for name, off_mesh in generated_meshes['fault'].items():
            filename = f"fault_{name}.off"
            full_path = os.path.join(out_dir, filename)
            with open(full_path, 'wb') as f:
                f.write(off_mesh)
            generated_meshes_paths['fault'][name].append(full_path)

        # write meta json
        with open(os.path.join(out_dir, 'index.json'), 'w', encoding='utf8') as f:
            json.dump(generated_meshes_paths, f, indent=2)

    if computation == 'voxels':
        # Call: main.py voxels [configuration_path] [geological_model_path] [surface_model_path] [meshes_folder] [out_file]
        # Inside meshes_folder, GWB meshes have the following syntax: f"mesh_{id}_{subID}.off"
        with open(args[2], encoding='utf8') as f:
            data = json.load(f)
        with open(args[3], 'rb') as f:
            xml = f.read()
        with open(args[4], 'r', encoding='utf8') as f:
            dem = f.read()

        gwb_meshes = defaultdict(list)
        for fp in os.listdir(args[5]):
            if not fp.endswith('.off'):
                continue
            gwb_id = fp.split('_')[1]  # Syntax: f"mesh_{id}_{subID}.off"
            full_path = Path(args[5]).joinpath(fp)
            with open(full_path, encoding='utf8') as f:
                gwb_meshes[gwb_id].append(f.read())

        voxels = compute_voxels(data, xml, dem, gwb_meshes)

        with open(args[6], 'w', encoding='utf8') as f:
            f.write(voxels)
