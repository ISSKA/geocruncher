import numpy as np

from gmlib.GeologicalModel3D import GeologicalModel
from gmlib.GeologicalModel3D import Box
from gmlib.tesselate import tesselate_faults
from skimage.measure import marching_cubes
from gmlib.architecture import from_GeoModeller, make_evaluator, grid
from gmlib.utils.tools import BBox3

from .profiler.profiler import get_current_profiler
from .off import generate_off

# Constants
RANK_SKY = 0


def compute_ranks(res: (int, int, int), model: GeologicalModel, box: Box = None):
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
    return evaluator(grid(box, res))


def rescale_to_grid(verts, box: Box, shape: (int, int, int)):
    step_size = np.array([
        (box.xmax - box.xmin) / (shape[0] - 1),
        (box.ymax - box.ymin) / (shape[1] - 1),
        (box.zmax - box.zmin) / (shape[2] - 1)
    ])
    # The marching cubes uses an extended shape with a margin of one additional step on each side.
    # Thus we need to shift the mesh by one step size.
    return (verts * step_size) - step_size + np.array([box.xmin, box.ymin, box.zmin])


def generate_volumes(model: GeologicalModel, shape: (int, int, int), box: Box) -> {"mesh": dict[str, str], "fault": dict[str, str]}:
    """Generates topologically valid meshes for each unit in the model. Meshes are output in OFF format.

    Parameters:
        model: A valid GeologicalModel with a loaded surface model (DEM).
        shape: Number of samples for marching cubes (x,y,z)
        box: Custom box
    """
    ranks = compute_ranks(shape, model, box)
    ranks.shape = shape

    # FIXME: it would be cheaper to retrieve the ranks from the stratigraphy. Something like:
    # That is true, the current method becomes longer the higher the resolution, while this one is fast and consistant,
    # except we get names, not numbers. TBD if we can get the rank number from this
    # rank_values = []
    # for serie in model.pile.all_series:
    #    for formation in serie.formations:
    #        rank_values.append(formation)

    rank_values = np.unique(ranks)
    num_ranks = len(rank_values)
    out_files = {"mesh": {}, "fault": {}}

    get_current_profiler().profile('ranks')

    # to close bodies, we put them in a slightly bigger grid
    extended_shape = tuple(n + 2 for n in shape)

    for rank in rank_values:
        if rank == RANK_SKY:
            continue
        if model.pile.reference == "base":
            if rank == 0:
                rank_id = num_ranks - 1
            else:
                rank_id = rank - 1
        else:
            rank_id = rank

        volume = np.zeros(extended_shape, dtype=np.float32)
        volume[1:-1, 1:-1, 1:-1][ranks == rank] = 1

        get_current_profiler().profile('volume')

        # Using the lewiner variant leads to holes in the meshes which CGAL cannot handle
        # (Produces an error when reading the OFF in geo-algo/VK-Aquifers)
        # Gradient direction ensures normals point outwards. Otherwise, aquifers computation will be incorrect
        verts, faces = marching_cubes(
            volume, level=0.5, gradient_direction='ascent', method='lorensen')[:2]
        mesh = rescale_to_grid(verts, box, shape)
        get_current_profiler().profile('marching_cubes')

        # FIXME @lopez use pycgal on next line to extract verts and faces
        # we have our own "off" generation for now, because of precision issues with the CGAL implementation. Do not replace that for now
        off_mesh = generate_off(mesh, faces)
        out_files["mesh"][str(rank_id)] = off_mesh
        get_current_profiler().profile('generate_off')

    if len(model.faults.items()) > 0:
        # don't waste time generating faults if there are none
        # the setup for the generation takes a considerable amount of time, even if there is nothing to generate
        out_files['fault'] = generate_faults_files(model, shape, box)

    return out_files


def generate_faults_files(model: GeologicalModel, shape: (int, int, int), box: Box = None) -> dict[str, str]:
    box = box or model.getbox()
    faults = tesselate_faults(box, shape, model)

    get_current_profiler().profile('tesselate_faults')

    out_files = {}
    for name, fault in faults.items():
        if not fault.is_empty():
            fault_arr = fault.as_arrays()
            off_mesh = generate_off(fault_arr[0], fault_arr[1][0])
            out_files[name] = off_mesh
            get_current_profiler().profile('generate_off')
    return out_files
