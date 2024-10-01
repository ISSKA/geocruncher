from io import StringIO
import numpy as np
import pyvista as pv
import meshio
from gmlib.GeologicalModel3D import GeologicalModel, Box

from .profiler.profiler import get_current_profiler
from .off import read_off

class Voxels:
    @staticmethod
    def output(model: GeologicalModel, shape: (int, int, int), box: Box, gwb_meshes: dict[str, list[str]]) -> str:
        # we use numpy meshgrid to produce a regular grid
        # the output is a list containing a 3D array for each coordinate
        # if we want an evaluation on the center of the voxels
        # we would have to compute voxel dimensions
        dx = (box.xmax - box.xmin) / shape[0]
        dy = (box.ymax - box.ymin) / shape[1]
        dz = (box.zmax - box.zmin) / shape[2]

        x, y, z = np.meshgrid(
            np.arange(box.xmin + 0.5 * dx, box.xmax, dx),
            np.arange(box.ymin + 0.5 * dy, box.ymax, dy),
            np.arange(box.zmin + 0.5 * dz, box.zmax, dz),
        )

        # we transform the previous data into an array of 3D points
        # this could be vertices from an unstructured mesh or any other data
        xyz = np.stack((x, y, z), axis=-1)
        xyz.shape = (-1, 3)

        get_current_profiler().profile('grid')

        gwb_tags = [0] * xyz.shape[0]
        for gwb_id, meshes in gwb_meshes.items():
            for mesh_str in meshes:
                mesh = pv.from_meshio(read_off(mesh_str)).extract_geometry()
                points = pv.PolyData(xyz)
                get_current_profiler().profile('read_gwbs')

                inside_points = points.select_enclosed_points(
                    mesh, tolerance=0.00001)
                selected_points = inside_points["SelectedPoints"].astype(
                    np.uint16)  # cast array to int16 to avoid overflow error
                gwb_tags = [max(new_id, _id) for new_id, _id in zip(
                    selected_points * int(gwb_id), gwb_tags)]
                get_current_profiler().profile('test_inside_gwbs')

        ranks = list(map(lambda point:  model.rank(point, True), xyz))

        # More performant version but there is a bug with topography
        # cppmodel = from_GeoModeller(model)
        # evaluator = Evaluator(cppmodel)
        # ranks = evaluator(xyz) + 1
        get_current_profiler().profile('ranks')

        ranks_tags = list(zip(ranks, gwb_tags))

        # We sort the arrays in reverse-nested loop order where z ist the outer loop, y the middle and x the inner loop
        # So that we don't have to write index in the output file
        xyz, ranks_tags = zip(*sorted(zip(xyz, ranks_tags),
                              key=lambda tup: (tup[0][2], tup[0][1], tup[0][0])))

        data = ''.join([(str(r_t[0]) + ' ' + str(r_t[1]) + '\n')
                       for r_t in ranks_tags])
        vox = f"\
XMIN={box.xmin} XMAX={box.xmax} YMIN={box.ymin} YMAX={box.ymax} ZMIN={box.zmin} ZMAX={box.zmax} \
NUMBERX={shape[0]} NUMBERY={shape[1]} NUMBERZ={shape[2]} NOVALUE=0\n\
rank gwb_id\n\
{data}"
        get_current_profiler().profile('generate_vox')
        return vox
