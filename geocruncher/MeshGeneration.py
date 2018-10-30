import os
import numpy as np

from skimage.measure import marching_cubes_lewiner as marching_cubes
from gmlib.GeologicalModel3D import GeologicalModel
import MeshTools as MT
import MeshTools.CGALWrappers as CGAL

def generate_volumes(model: GeologicalModel, shape: (int,int,int), outDir: str):
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
        return points * np.array([
            (box.xmax - box.xmin) / (nx - 1),
            (box.ymax - box.ymin) / (ny - 1),
            (box.zmax - box.zmin) / (nz - 1),
        ]) + np.array([box.xmin, box.ymin, box.zmin])

    def get_model_ranks(model):
        num_formations = sum([ len(s.formations) for s in model.pile.all_series ])
        return list(range(RANK_SKY + 1, num_formations + 1))

    nx, ny, nz = shape
    box = model.getbox()
    steps = (
        np.linspace(box.xmin, box.xmax, nx),
        np.linspace(box.ymin, box.ymax, ny),
        np.linspace(box.zmin, box.zmax, nz),
    )
    coordinates = np.meshgrid(*steps, indexing='ij')
    points = np.stack(coordinates, axis=-1)
    points.shape = (-1, 3)

    ranks = get_model_ranks(model)

    bodies = []
    for rank in ranks:
        # to close bodies, we put them in a slightly bigger grid
        extended_shape = tuple(n+2 for n in shape)
        indicator = np.zeros(extended_shape, dtype=np.float32)
        indicator[1:-1, 1:-1, 1:-1][ranks==rank] = 1

        verts, faces, normals, values = marching_cubes(indicator, level=0.5, gradient_direction="ascent") # Gradient direction ensures normals point outwards
        tsurf = CGAL.TSurf(rescale_to_grid(verts, box, shape), faces)
        bodies.append(tsurf)

    out_files = []
    for bi, body in enumerate(bodies):
        name = 'body_rank_%d' % bi
        out_file = os.path.join(outDir, name + '.off')
        body.to_off(out_file)
        out_files.append(out_file)

    return out_files
