import json
import os
from collections import defaultdict

import MeshTools.CGALWrappers as CGAL
import numpy as np
from gmlib.GeologicalModel3D import GeologicalModel
from gmlib.GeologicalModel3D import Box
from gmlib.tesselate import tesselate_faults
from gmlib.tesselate import Tesselator
from gmlib.tesselate import TopographyClipper
from gmlib.architecture import from_GeoModeller, make_evaluator
from skimage.measure import marching_cubes_lewiner as marching_cubes

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

    cppmodel = from_GeoModeller(model)
    topography = model.implicit_topography() # <- NB: here we could use an alternate topography
    evaluator = make_evaluator(cppmodel, topography)
    ranks = evaluator(points)
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
        verts, faces, normals, values = marching_cubes(indicator, level=0.5, gradient_direction="ascent", use_classic=True)  # Gradient direction ensures normals point outwards
        tsurf = CGAL.TSurf(rescale_to_grid(verts, box, shape), faces)

        # Repair mesh if there are border edges. Mesh must be closed.
        if not tsurf.is_closed():
            CGAL.fix_border_edges(tsurf)

        meshes[rankId] = tsurf

    out_files = {"mesh": defaultdict(list), "fault": generate_faults_files(model, shape, outDir, optBox)}
    for rank, mesh in meshes.items():
        filename = 'rank_%d.off' % rank
        out_file = os.path.join(outDir, filename)
        mesh.to_off(out_file)
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
    if optBox:
        box = optBox
        faults = tesselate_faults_smaller(box, (nx, ny, nz), model)
    else:
        box = model.getbox()
        faults = tesselate_faults(box, (nx, ny, nz), model)
    out_files = defaultdict(list)
    for name, fault in faults.items():
        filename = 'fault_%s.off' % name
        out_file = os.path.join(outDir, filename)
        fault.write_off(out_file)
        out_files[name].append(out_file)
    return out_files

# Here we override tesselate faults method to take the SmallBoxTesselator
# which will just try/catch fault to meshes method, so that we do not 
# get an error if the fault is outside the smaller box
def tesselate_faults_smaller(box, shape, model, clip_topography=True):
    tesselator = SmallBoxTesselator(box, shape)
    topography = (
        TopographyClipper(model.topography, tesselator.tesselate_topography(model))
        if clip_topography
        else None
    )
    return tesselator.tesselate_faults(model, topography)


class SmallBoxTesselator(Tesselator):
    def tesselate_faults(self, model, topography=None):
        fault_tesselations = {}
        for name, field in model.faults.items():
            try:
                fault_tesselations[name] = self(field, 0)
            except ValueError:
                pass
        for name, surface in fault_tesselations.items():
            if topography:
                surface = topography.clip(surface)
            data = model.faults_data[name]
            assert len(data.potential_data.interfaces) == 1
            fault_points = data.potential_data.interfaces[0]
            for limit_name in data.stops_on:
                try:
                    limit_surface = fault_tesselations[limit_name]
                    CGAL.corefine(surface, limit_surface)
                    limit_fault = model.faults[limit_name]
                    limit_field_values = limit_fault(surface.face_centers())
                    if np.mean(limit_fault(fault_points)) < 0:
                        surface.remove_faces(limit_field_values > 0)
                    else:
                        surface.remove_faces(limit_field_values < 0)
                except KeyError:
                    pass
        return fault_tesselations
