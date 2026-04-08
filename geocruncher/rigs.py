from forgeo.gmlib.GeologicalModel3D import GeologicalModel, Box
from forgeo.rigs import all_intersections
from forgeo.rigs.tetcube import tetgrid
from forgeo.rigs.gmconverter import convert


# TODO: more accurate typings for the returned values
def extract(
    model: GeologicalModel,
    shape: tuple[int, int, int],
    box: Box = None,
    faults_only=False,
) -> tuple[list, list, list, list]:
    """Generate a regular grid of tesselated cubes, convert the model to RIGS and evaluate it on the grid, returning surfaces

    Returns vertices, faces, parts and surface_names
    You can determine to which part each face belongs with the third return value (parts). For each face, it is an index in the forth return value (surface_names), which corresponds to units, faults, and the "topography"

    The returned unit names are prefixed with the pile reference and a dash (ex: "base-Molasse")

    Parameters:
        model: A valid GeologicalModel with a loaded surface model (DEM).
        shape: Size of the regular grid of tesselated cubes. (x,y,z)
        box: Custom box. Optional
        faults_only: If True, only faults will be computed and returned. Defaults to False

    Returns:
        Tuple[list, list, list, list]: (vertices, faces, parts, surface_names)
        1) 3d points representing mesh vertices
        2) references to vertices that form polygons (tris, quads & ngons possible)
        3) index in surface_names for each face, to determine to which surface it belongs
        4) the list of surfaces that might be present in the output
    """

    box = model.getbox() if box is None else box
    vertices, cells = tetgrid(
        shape,
        extent=(box.xmin, box.xmax, box.ymin, box.ymax, box.zmin, box.zmax),
    )

    params = convert(model, with_topography=True, faults_only=faults_only)
    results = all_intersections(vertices, cells, **params, return_iso_surfaces=True)

    iso = results.iso_surfaces
    return (
        iso.vertices,
        iso.faces,
        iso.color,
        params["names"],
    )
