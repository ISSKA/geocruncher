from .GeologicalModel3D import GeologicalModel
from forgeo.gmlib.GeologicalModel3D import Box
from forgeo.rigs import all_intersections
from forgeo.rigs.tetcube import tetgrid
from forgeo.rigs.gmconverter import convert


def extract(
    model: GeologicalModel,
    shape: tuple[int, int, int],
    box: Box = None,
    faults_only=False,
):

    box = model.getbox() if box is None else box
    vertices, cells = tetgrid(
        shape,
        extent=(box.xmin, box.xmax, box.ymin, box.ymax, box.zmin, box.zmax),
    )

    print("before convert")
    params = convert(model, with_topography=True, faults_only=faults_only)
    print(params)

    print("before intersections")
    results = all_intersections(vertices, cells, **params, return_iso_surfaces=False)

    iso = results.iso_surfaces
    return iso.vertices, iso.faces, iso.color, params["colors"]
