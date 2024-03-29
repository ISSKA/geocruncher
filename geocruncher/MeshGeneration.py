import json
import os
from collections import defaultdict

import MeshTools.CGALWrappers as CGAL
import numpy as np

import gmlib

assert gmlib.__version__ >= "0.3.11"
from gmlib.GeologicalModel3D import GeologicalModel
from gmlib.GeologicalModel3D import Box
from gmlib.tesselate import tesselate_faults
from skimage.measure import marching_cubes
from gmlib.architecture import from_GeoModeller, make_evaluator, grid
from gmlib.utils.tools import BBox3


def generate_off(verts, faces, precision=3):
    """Generates a valid OFF string from the given verts and faces.

    Parameters:
        verts: (V, 3) array
            Spatial coordinates for V unique mesh vertices. Coordinate order
            must be (x, y, z).
        faces: (F, N) array
            Define F unique faces of N size via referencing vertex indices from ``verts``.
        precision: int
            How many decimals to keep when writing vertex position. Defaults to 3.

    Returns:
        str: A valid OFF string.
    """
    # Implementation reference: https://en.wikipedia.org/wiki/OFF_(file_format)#Composition
    num_verts = len(verts)
    num_faces = len(faces)
    v = '\n'.join([' '.join([str(round(float(position), precision)) for position in vertex]) for vertex in verts])
    f = '\n'.join([' '.join([str(len(face)), *(str(int(index)) for index in face)]) for face in faces])

    return "OFF\n{num_verts} {num_faces} 0\n{vertices}\n{faces}\n".format(
        num_verts=num_verts,
        num_faces=num_faces,
        vertices=v,
        faces=f)


def _compute_ranks(res, model, box=None):
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


def generate_volumes(model: GeologicalModel, shape: (int, int, int), outDir: str, optBox: Box = None):
    """Generates topologically valid meshes for each unit in the model. Meshes are output in OFF format.

    Parameters:
        model: A valid GeologicalModel with a loaded surface model (DEM).
        shape: Number of samples for marching cubes (x,y,z)
        outDir: Path where to store generated mesh files

    Returns:
        list: path of each generated mesh.
    """

    # Constants
    RANK_SKY = 0

    def rescale_to_grid(points, box, shape):
        nx, ny, nz = shape
        stepSize = np.array([
            (box.xmax - box.xmin) / (nx - 1),
            (box.ymax - box.ymin) / (ny - 1),
            (box.zmax - box.zmin) / (nz - 1)
        ])
        # The marching cubes uses an extended shape with a margin of one additional step on each side.
        # Thus we need to shift the mesh by one step size.
        return (points * stepSize) - stepSize + np.array([box.xmin, box.ymin, box.zmin])

    nx, ny, nz = shape
    if optBox:
        box = optBox
    else:
        box = model.getbox()
    steps = (
        np.linspace(box.xmin, box.xmax, nx),
        np.linspace(box.ymin, box.ymax, ny),
        np.linspace(box.zmin, box.zmax, nz),
    )
    coordinates = np.meshgrid(*steps, indexing='ij')
    points = np.stack(coordinates, axis=-1)
    points.shape = (-1, 3)

    ranks = _compute_ranks(shape, model, box)
    ranks.shape = shape

    # FIXME: it would be cheaper to retrieve the ranks from the stratigraphy. Something like:
    # rank_values = []
    # for serie in model.pile.all_series:
    #    for formation in serie.formations:
    #        rank_values.append(formation)

    rank_values = np.unique(ranks)
    meshes = {}
    for rank in rank_values:
        if rank == RANK_SKY:
            continue
        if model.pile.reference == "base":
            if rank == 0:
                rankId = len(rank_values) - 1
            else:
                rankId = rank - 1
        else:
            rankId = rank

        # to close bodies, we put them in a slightly bigger grid
        extended_shape = tuple(n + 2 for n in shape)
        indicator = np.zeros(extended_shape, dtype=np.float32)
        indicator[1:-1, 1:-1, 1:-1][ranks == rank] = 1

        # Using the non-classic variant leads to holes in the meshes which CGAL cannot handle
        # the classic variant seems to work better for us
        verts, faces, normals, values = marching_cubes(indicator, level=0.5, gradient_direction="ascent", method="lorensen")  # Gradient direction ensures normals point outwards
        tsurf = CGAL.TSurf(rescale_to_grid(verts, box, shape), faces)

        # Repair mesh if there are border edges. Mesh must be closed.
        if not tsurf.is_closed():
            CGAL.fix_border_edges(tsurf)

        meshes[rankId] = tsurf

    out_files = {"mesh": defaultdict(list), "fault": generate_faults_files(model, shape, outDir, optBox)}
    for rank, mesh in meshes.items():
        filename = 'rank_%d.off' % rank
        out_file = os.path.join(outDir, filename)

        off_mesh = generate_off(*mesh.as_arrays())
        with open(out_file, 'w', encoding='utf8') as f:
            f.write(off_mesh)
        out_files["mesh"][str(rank)].append(out_file)

    with open(os.path.join(outDir, 'index.json'), 'w') as f:
        json.dump(out_files, f, indent=2)

    return out_files


def generate_faults(model: GeologicalModel, shape: (int, int, int), outDir: str):
    out_files = {"mesh": defaultdict(list), "fault": generate_faults_files(model, shape, outDir)}
    with open(os.path.join(outDir, 'index.json'), 'w') as f:
        json.dump(out_files, f, indent=2)

    return out_files


def generate_faults_files(model: GeologicalModel, shape: (int, int, int), outDir: str, optBox: Box = None):
    nx, ny, nz = shape
    box = optBox or model.getbox()
    faults = tesselate_faults(box, (nx, ny, nz), model)
    out_files = defaultdict(list)
    for name, fault in faults.items():
        if not fault.is_empty():
            filename = 'fault_%s.off' % name
            out_file = os.path.join(outDir, filename)
            fault_arr = fault.as_arrays()
            off_mesh = generate_off(fault_arr[0], fault_arr[1][0])
            with open(out_file, 'w', encoding='utf8') as f:
                f.write(off_mesh)
            out_files[name].append(out_file)
    return out_files
