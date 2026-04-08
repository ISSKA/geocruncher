import numpy as np
from collections import defaultdict

from forgeo.gmlib.GeologicalModel3D import GeologicalModel, Box

from skimage.measure import marching_cubes
from forgeo.gmlib.architecture import from_GeoModeller, make_evaluator, grid
from forgeo.gmlib.utils.tools import BBox3

from .profiler import profile_step
from .mesh_io.mesh_io import generate_mesh
from .rigs import extract


# Constants
RANK_SKY = 0


def compute_ranks(res: tuple[int, int, int], model: GeologicalModel, box: Box = None):
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


def rescale_to_grid(verts, box: Box, shape: tuple[int, int, int]):
    step_size = np.array([
        (box.xmax - box.xmin) / (shape[0] - 1),
        (box.ymax - box.ymin) / (shape[1] - 1),
        (box.zmax - box.zmin) / (shape[2] - 1)
    ])
    # The marching cubes uses an extended shape with a margin of one additional step on each side.
    # Thus we need to shift the mesh by one step size.
    return (verts * step_size) - step_size + np.array([box.xmin, box.ymin, box.zmin])


def generate_volumes(
    model: GeologicalModel, shape: tuple[int, int, int], box: Box
) -> {"mesh": dict[str, bytes], "fault": dict[str, bytes]}:
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

    profile_step('ranks')

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

        profile_step('volume')

        # Using the lewiner variant leads to holes in the meshes which CGAL cannot handle
        # (Produces an error when reading the OFF in geo-algo/VK-Aquifers)
        # Gradient direction ensures normals point outwards. Otherwise, aquifers computation will be incorrect
        verts, faces = marching_cubes(
            volume, level=0.5, gradient_direction='ascent', method='lorensen')[:2]
        scaled_verts = rescale_to_grid(verts, box, shape)
        profile_step('marching_cubes')

        mesh = generate_mesh(scaled_verts, faces)
        out_files["mesh"][str(rank_id)] = mesh
        profile_step('generate_mesh')

    if len(model.faults.items()) > 0:
        # don't waste time generating faults if there are none
        # the setup for the generation takes a considerable amount of time, even if there is nothing to generate
        out_files['fault'] = generate_faults_files(model, shape, box)

    return out_files


# Currently unused, for future reference and testing. Drop-in replacement for "generate_volumes", but currently returns surfaces and not volumes (not yet implemented in rigs)
def generate_rigs_volumes(
    model: GeologicalModel, shape: tuple[int, int, int], box: Box = None
) -> {"mesh": dict[str, bytes], "fault": dict[str, bytes]}:
    """Generates topologically valid meshes for each unit in the model. Meshes are output in Draco format.

    Parameters:
        model: A valid GeologicalModel with a loaded surface model (DEM).
        shape: Size of the regular grid of tesselated cubes. (x,y,z)
        box: Custom box. Optional
    """
    out_files = {"mesh": {}, "fault": {}}
    is_top = model.pile.reference == "top"

    # Create a map from unit name to unit id, as we want to return the meshes indexed by this id, but in rigs we identify them through their name
    unit_names = model.pile_formations
    unit_id = {}
    for i, n in enumerate(unit_names):
        unit_id[n] = i + 1 if is_top else i
    # Rigs returns units and faults mixed up, so we need to know which faults exist
    fault_names = list(model.faults.keys())

    # The rigs name is the pile reference dash the unit name
    prefix = model.pile.reference + "-"

    # The biggest par of the job is done here. Convert to rigs data structure and extract surfaces
    v, f, parts, surface_names = extract(model, shape, box)

    # The returned data is one big list of vertices and faces for all parts. We can separate the faces by part using an identifier per face.
    grouped = defaultdict(list)
    for i, fi in enumerate(f):
        grouped[parts[i]].append(fi)

    # Then separate the result into the relevant units/faults and generate Draco meshes for each
    for part in grouped.keys():
        try:
            prefixed_name = surface_names[part]
            print(f"Extracting part {part} with name {prefixed_name}")
        except IndexError:
            # Can happen when messing with rigs input parameters. should not happen in prod
            print(f"Ignoring part {part} with unknown name")
            continue

        mesh = generate_mesh(v, grouped[part])

        # We can know which unit/fault the part represents, as the identifier is the index in surface_names
        # Since units and faults are mixed, we need to figure out which type this is
        if prefixed_name in fault_names:
            # faults are indexed by their name
            out_files["fault"][prefixed_name] = mesh
        else:
            try:
                # Remove the prefix in order to look up the unit id from the original name
                name = prefixed_name[len(prefix) :]
                # Units are indexed by their unit id (sequence based on pile order)
                out_files["mesh"][str(unit_id[name])] = mesh
            except KeyError:
                # The list can also contain "topography", which represents the DEM. We don't want to save that
                # Can be saved to index 0 for debug, this makes it the dummy mesh
                # out_files["mesh"][str(0)] = mesh
                continue

    return out_files


def generate_faults_files(
    model: GeologicalModel, shape: tuple[int, int, int], box: Box = None
) -> dict[str, bytes]:
    # For now, the resolution of faults is 10x lower than the mesh, with a minimum of 10, as with RIGS, we see no improvements with increased resolution except for conformity with the DEM and higher resolutions are extremely slow
    rigs_shape = (
        int(max(10, shape[0] / 10)),
        int(max(10, shape[1] / 10)),
        int(max(10, shape[2] / 10)),
    )
    v, f, parts, surface_names = extract(model, rigs_shape, box, faults_only=True)

    profile_step('tesselate_faults')

    # The returned data is one big list of vertices and faces for all parts. We can separate the faces by part using an identifier per face.
    grouped = defaultdict(list)
    for i, fi in enumerate(f):
        grouped[parts[i]].append(fi)

    out_files = {}

    for part in grouped.keys():
        # We can know which unit/fault the part represents, as the identifier is the index in surface_names
        # Here we only computed faults therefore we assume every returned part is a valid fault. There is a bit more checking if we compute both units & faults
        name = surface_names[part]
        mesh = generate_mesh(v, grouped[part])
        out_files[name] = mesh

    return out_files
