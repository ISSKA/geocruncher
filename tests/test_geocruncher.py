import geocruncher.main as main
import pytest

import shutil
import os

def test_geocruncher():
    main.run_geocruncher(['', 'all', 'tests/dummy_project/sections.json', 'tests/dummy_project/geocruncher_project.xml', 'tests/dummy_project/geocruncher_dem.asc', 'test_output.json'])

def test_mesh_generation():
    base_dir = os.path.join(os.getcwd(), 'tests')
    project_file = os.path.join(base_dir, 'dummy_project', 'geocruncher_project.xml')
    dem_file = os.path.join(base_dir, 'dummy_project', 'geocruncher_dem.asc')
    out_dir = os.path.join(base_dir, 'meshes_out')

    shutil.rmtree(out_dir, ignore_errors=True)
    os.mkdir(out_dir)
    main.run_geocruncher(['', 'meshes', '5', project_file, dem_file, out_dir])

    out_files = os.listdir(out_dir)
    num_mesh_files = len([f for f in out_files if f.lower().endswith('.off')])
    shutil.rmtree(out_dir, ignore_errors=True)

    assert num_mesh_files > 0
