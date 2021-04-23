import sys
import os
import numpy as np
from gmlib.GeologicalModel3D import GeologicalModel
from gmlib.architecture import from_GeoModeller, Evaluator
from time import perf_counter
import pyvista as pv
import pymeshfix


def _compute_voxels(res, box, model, meshes_files, out_file, USE_HIGH_RES=True):
    # args: [1] resolution [2] box 3d of the projet [3] model geologic of the project [4] list of filename of meshes [5] folder to create outpout file
    # [6] write voxel indices to file default False, [7] use decimated mesh default True
    nx, ny, nz = res
    total_start = perf_counter()

    # we use numpy meshgrid to produce a regular grid
    # the output is a list containing a 3D array for each coordinate
    # if we want an evaluation on the center of the voxels
    # we would have to compute voxel dimensions
    dx = (box.xmax - box.xmin) / nx
    dy = (box.ymax - box.ymin) / ny
    dz = (box.zmax - box.zmin) / nz

    x, y, z = np.meshgrid(
        np.arange(box.xmin + 0.5 * dx, box.xmax, dx),
        np.arange(box.ymin + 0.5 * dy, box.ymax, dy),
        np.arange(box.zmin + 0.5 * dz, box.zmax, dz),
    )

    # we transform the previous data into an array of 3D points
    # this could be vertices from an unstructured mesh or any other data
    #xyz = np.hstack(np.reshape(coord, (-1, 1)) for coord in (x, y, z))
    xyz = np.stack((x, y, z), axis=-1)
    xyz.shape = (-1, 3)

    t1_start = perf_counter()
    gwb_tags = [0] * xyz.shape[0]
    for mesh_file in meshes_files:
        gwb_id = int(mesh_file.split("_")[1])
        mesh = pv.read(mesh_file)
        mesh = mesh.extract_geometry()
        points = pv.PolyData(xyz)

        insidePoints = None
        if not USE_HIGH_RES:
            decimated = mesh.decimate(0.9)
            fixer = pymeshfix.MeshFix(decimated)
            mesh = fixer.repair(joincomp=True, remove_smallest_components=False)

        insidePoints = points.select_enclosed_points(mesh, tolerance=0.00001)
        print(len(insidePoints.threshold(0.5).points))
        gwb_tags = [max(newId, _id) for newId, _id in zip(insidePoints["SelectedPoints"] * gwb_id, gwb_tags)]

    t1_stop = perf_counter()
    print("Elapsed time GWB mesh IN or OUT test", t1_stop - t1_start)

    t1_start = perf_counter()
    # this is to be replaced soon by an optimized function
    ranks = list(map(lambda point:  model.rank(point, True), xyz))

    # More performant version need some testing
    # Ignore topography ???
    # cppmodel = from_GeoModeller(model)
    # evaluator = Evaluator(cppmodel)
    # ranks = evaluator(xyz) + 1

    ranks_tags = list(zip(ranks, gwb_tags))
    t1_stop = perf_counter()
    print("Elapsed time discretisation:", t1_stop-t1_start)

    # We sort the arrays in reverse-nested loop order where z ist the outer loop, y the middle and x the inner loop
    # So that we don't have to write index in the output file
    t1_start = perf_counter()
    xyz, ranks_tags = zip(*sorted(zip(xyz, ranks_tags), key=lambda tup: (tup[0][2], tup[0][1], tup[0][0])))
    t1_stop = perf_counter()
    print("Elapsed time sorting:", t1_stop - t1_start)

    t1_start = perf_counter()
    data = ''.join([(str(r_t[0]) + ' ' + str(r_t[1]) + '\n') for r_t in ranks_tags])

    with open(out_file, 'w') as outfile:
        outfile.write('XMIN={0} XMAX={1} YMIN={2} YMAX={3} ZMIN={4} ZMAX={5}'
                      .format(box.xmin, box.xmax, box.ymin, box.ymax, box.zmin, box.zmax))
        outfile.write(' NUMBERX={0} NUMBERY={1} NUMBERZ={2} NOVALUE={3}\n'.format(nx, ny, nz, 0))
        outfile.write('rank gwb_id\n')
        outfile.write(data)

    t1_stop = perf_counter()
    print("Elapsed time writing to file:", t1_stop - t1_start)
    total_stop = perf_counter()
    print("Total elapsed time", total_stop - total_start)
