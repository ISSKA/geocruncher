import os
import numpy as np

from skimage.measure import marching_cubes_lewiner as marching_cubes
from gmlib.GeologicalModel3D import GeologicalModel
import MeshTools as MT
import MeshTools.CGALWrappers as CGAL

class MeshGeneration:

    def generate(self, model: GeologicalModel, shape: (int,int,int), outDir: str):
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

        ranks = np.array([model.rank(P) for P in points])
        ranks.shape = shape

        # FIXME: it would be cheaper to access the geological pile
        rank_values = np.unique(ranks)
        bodies = []
        for rank in rank_values:
            # to *close* bodies we put them in a slightly bigger grid
            extended_shape = tuple(n+2 for n in shape)
            indicator = np.zeros(extended_shape, dtype=np.float32)
            indicator[1:-1, 1:-1, 1:-1][ranks==rank] = 1
            verts, faces, normals, values = marching_cubes(indicator, level=0.5)
            tsurf = CGAL.TSurf(rescale(verts, box, shape), faces)
            if options.check_orientation:
                s = options.check_orientation.lower()
                if s.startswith("out"):
                    tsurf.orient(True)
                elif s.startswith("in"):
                    tsurf.orient(False)
                else:
                    raise IOError('could not decode orientation from string ' + check_orientation)
        bodies.append(tsurf)

        for bi, body in enumerate(bodies):
            # TODO Use unit name from column?
            fiename = 'body_rank_%d' % bi
            outFile = os.path.join(outDir, name + '.off')
            surface.to_off(outFile)
