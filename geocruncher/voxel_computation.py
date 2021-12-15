import sys
import os
import numpy as np
from gmlib.GeologicalModel3D import GeologicalModel
from gmlib.architecture import from_GeoModeller, make_evaluator, grid
from gmlib.utils.tools import BBox3
import pyvista as pv

# Need to find the order to be used
# From gmlib v0.3.8, given a model you can ask its bounding box (model.bbox())
# and then compute a grid from the box and a shape with grid(box, shape)
# then pass the grid to the evaluator
def _compute_voxels_ranks(res, model, box=None):
    """"
    :param res: resolution (supposed to be a tuple)
    :param model: gmlib.GeologicalModel object
    :param box: if not given will default to the bounding box of model 
    """
    if box is None:
        box = model.bbox()
    else:
        box = BBox3(box.xmin, box.xmax, box.ymin, box.ymax, box.zmin, box.zmax)
    cppmodel = from_GeoModeller(model)
    topography = model.implicit_topography()
    evaluator = make_evaluator(cppmodel, topography)
    return evaluator(grid(box, res, centered=True))


def _compute_voxels(res, box, model, meshes_files, out_file):
    # args: [1] resolution [2] box 3d of the projet [3] model geologic of the project [4] list of filename of meshes [5] output file
    nx, ny, nz = res

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
    xyz = np.stack((x, y, z), axis=-1)
    xyz.shape = (-1, 3)

    gwb_tags = [0] * xyz.shape[0]
    for mesh_file in meshes_files:
        gwb_id = int(mesh_file.split("_")[1])
        mesh = pv.read(mesh_file)
        mesh = mesh.extract_geometry()
        points = pv.PolyData(xyz)

        insidePoints = points.select_enclosed_points(mesh, tolerance=0.00001)
        gwb_tags = [max(newId, _id) for newId, _id in zip(insidePoints["SelectedPoints"] * gwb_id, gwb_tags)]

    # OLD working version
    #ranks = list(map(lambda point:  model.rank(point, True), xyz))

    # More performant version but there is a bug with topography
    cppmodel = from_GeoModeller(model)
    topography = model.implicit_topography()  # <- NB: here we could use an alternate topography
    evaluator = make_evaluator(cppmodel, topography)
    ranks = evaluator(xyz)

    #ranks = _compute_voxels_ranks(res, model, box)
    ranks.shape = (-1)

    ranks_tags = list(zip(ranks, gwb_tags))

    # We sort the arrays in reverse-nested loop order where z ist the outer loop, y the middle and x the inner loop
    # So that we don't have to write index in the output file
    xyz, ranks_tags = zip(*sorted(zip(xyz, ranks_tags), key=lambda tup: (tup[0][2], tup[0][1], tup[0][0])))

    data = ''.join([(str(r_t[0]) + ' ' + str(r_t[1]) + '\n') for r_t in ranks_tags])

    with open(out_file, 'w') as outfile:
        outfile.write('XMIN={0} XMAX={1} YMIN={2} YMAX={3} ZMIN={4} ZMAX={5}'
                      .format(box.xmin, box.xmax, box.ymin, box.ymax, box.zmin, box.zmax))
        outfile.write(' NUMBERX={0} NUMBERY={1} NUMBERZ={2} NOVALUE={3}\n'.format(nx, ny, nz, 0))
        outfile.write('rank gwb_id\n')
        outfile.write(data)
