import math

import numpy as np
import pyvista as pv
from gmlib.GeologicalModel3D import GeologicalModel, Box
from gmlib.architecture import from_GeoModeller, make_evaluator

from .profiler.profiler import get_current_profiler
from .mesh_io.mesh_io import read_mesh_to_polydata

def calculate_resolution(width: float, height: float, res: int) -> tuple[int, int]:
    """Calculates a proportional resolution where the larger dimension matches `res`.
    
    The smaller dimension is scaled to maintain the original aspect ratio, with rounding
    to the nearest integer.

    Args:
        width: Original width (float, accepts non-integer ratios).
        height: Original height (float, accepts non-integer ratios).
        res: Target resolution (int) for the larger dimension.

    Returns:
        Tuple[int, int]: New (width, height) where one dimension equals `res`.
    """
    if width >= height:
        new_width = res
        new_height = int(round(height * (res / width)))
    else:
        new_height = res
        new_width = int(round(width * (res / height)))
    return (new_width, new_height)

def compute_vertical_slice_points(
    x_coord: tuple[int, int],
    y_coord: tuple[int, int],
    z_coord: tuple[int, int],
    resolution: tuple[int, int]
) -> np.ndarray:
    """Calculate 3D points along a vertical slice plane.

    Parameters
    ----------
    x_coord : tuple[int, int]
        Start and end x-coordinates of the slice line.
    y_coord : tuple[int, int]
        Start and end y-coordinates of the slice line.
    z_coord : tuple[int, int]
        Start and end z-coordinates defining the vertical range of the slice.
    resolution : tuple[int, int]
        Width resolution and Height resolution.

    Returns
    -------
    np.ndarray
        Array of shape (resolution[0]*resolution[1], 3) containing the (x, y, z) coordinates of points
        in the slice plane.

    Notes
    -----
    For non-y-axis-aligned slices, points are computed using the slope between
    start and end coordinates. For y-axis-aligned slices, x remains constant
    while y varies linearly.
    """
    z_slice_range = np.linspace(z_coord[0], z_coord[1], resolution[1])

    if not x_coord[0] == x_coord[1]:
        x_slice_range = np.linspace(x_coord[0], x_coord[1], resolution[0])
        slope = (y_coord[0] - y_coord[1]) / (x_coord[0] - x_coord[1])
        z, x = np.meshgrid(z_slice_range, x_slice_range)
        y = slope * (x - x_coord[0]) + y_coord[0]
    else:
        y_slice_range = np.linspace(y_coord[0], y_coord[1], resolution[0])
        z, y = np.meshgrid(z_slice_range, y_slice_range)
        x = np.full_like(y, x_coord[0])
    xyz = np.stack((x.ravel(), y.ravel(), z.ravel()), axis=-1)
    return xyz

def compute_map_points(box: Box, resolution: tuple[int, int], model: GeologicalModel) -> np.ndarray:
    """Compute points for a top-down geological cross section.

    Parameters
    ----------
    box : Box
        The bounding box of the geological model.
    resolution : tuple[int, int]
        Width resolution and Height resolution.
    model : gmlib.GeologicalModel3D.GeologicalModel
        The GeologicalModel from gmlib to use for the topography evaluation.
    
    Returns
    -------
    np.ndarray
        A numpy array of shape (resolution[0]*resolution[1], 3) containing the (x, y, z) coordinates of the points.
    
    Notes
    -----
    The z coordinate is evaluated using the topography of the geological model.
    The returned points are ordered in a grid pattern, sorted by x, then y.
    """

    x_map_range = np.linspace(box.xmin, box.xmax, resolution[0])
    y_map_range = np.linspace(box.ymin, box.ymax, resolution[1])
    y, x = np.meshgrid(y_map_range, x_map_range)
    xy = np.stack([x.ravel(), y.ravel()], axis=1)
    z = model.topography.evaluate_z(xy)
    xyz = np.column_stack((xy, z))
    return xyz

def compute_cross_section_ranks(
    xyz: np.ndarray,
    resolution: tuple[int, int],
    model: GeologicalModel,
    topography: bool = False
) -> list:
    """Compute formation ranks for a geological cross section.

    Parameters
    ----------
    xyz : np.ndarray
       Array of 3D coordinates where the ranks will be evaluated, shape (resolution[0]*resolution[1], 3)
    resolution : tuple[int, int]
        x is the width resolution, y is the height resolution.
    model : gmlib.GeologicalModel3D.GeologicalModel
        The GeologicalModel from gmlib to use for the formation rank evaluation.
    topography : bool, optional
        If True, the topography of the geological model will be used for rank evaluation.
        Default is False.

    Returns
    -------
    list
        A list of ranks after evaluation, reshaped to resolution.

    Notes
    -----
    For top-down views the topography should be False and for vertical slices it should be True.
    """

    cppmodel = from_GeoModeller(model)
    if topography:
        topography = model.implicit_topography()
        evaluator = make_evaluator(cppmodel, topography)
    else:
        evaluator = make_evaluator(cppmodel)

    is_base = model.pile.reference == 'base'
    rank_offset = -1 if is_base else 0

    ranks = evaluator(xyz) + rank_offset
    ranks.shape = resolution
    ranks = ranks.tolist()
    get_current_profiler().profile('cross_section_ranks')
    return ranks


def project_hydro_features_on_slice(
    lower_left: np.ndarray,
    upper_right: np.ndarray,
    xyz: np.ndarray,
    spring_map: dict,
    drillhole_map: dict,
    gwb_meshes: dict[str, list[bytes]],
    max_dist_proj: float
) -> tuple[dict, dict, list]:
    """Project hydrogeological features onto a vertical cross section plane.

    Parameters
    ----------
    lower_left : np.ndarray
        The lower left corner coordinates of the cross section
    upper_right : np.ndarray
        The upper right corner coordinates of the cross section
    xyz : np.ndarray
        Array of shape (N, 3) containing the (x, y, z) coordinates of points of the cross section
    spring_map : dict
        Dictionary of spring data with coordinates
    drillhole_map : dict
        Dictionary of drill hole data with start and end coordinates
    gwb_meshes : dict[str, list[str]]
        Dictionary containing groundwater body IDs and their corresponding mesh strings in OFF or Draco format
    max_dist_proj : float
        Maximum projection distance for features

    Returns
    -------
    drillholes_line : dict
        Dictionary of projected drill holes with start and end coordinates
    springs_point : dict
        Dictionary of projected springs with coordinates
    matrix_gwb_combine : list
        List of groundwater body values for each point in rank_matrix
        each value corresponds to the groundwater body ID for that point
    """

    # Create a third point to define the plane
    # The third point is the same x and y as the lower left corner, but z is the upper right corner
    # This is possible because cross sections are always parallel to the z axis
    p0 = np.array(lower_left)
    p1 = np.array(upper_right)
    p2 = np.array([lower_left[0], lower_left[1], upper_right[2]])

    # Pre-compute plane normal vector once
    plane_normal = np.cross(np.subtract(p1, p0), np.subtract(p2, p0))
    plane_normal = plane_normal / np.linalg.norm(plane_normal)

    def _proj_point_on_plane(q: np.ndarray) -> tuple[list, bool]:
        """Project a point onto the section plane and check if it's within threshold.

        Parameters
        ----------
        q : np.ndarray
            The 3D point to project

        Returns
        -------
        Tuple[list, bool]
            Projected 2D coordinates and boolean indicating if projection is valid
        """
        q_to_p0 = np.subtract(q, p0)
        dist_to_plane = np.dot(q_to_p0, plane_normal)
        q_proj = np.subtract(q, dist_to_plane * plane_normal)
        proj_distance = np.linalg.norm(np.subtract(q, q_proj))
        valid = proj_distance < max_dist_proj
        return _transform_value(q_proj), valid

    def _transform_value(q: np.ndarray) -> list:
        """Transform a 3D point into 2D section coordinates.

        Parameters
        ----------
        q : np.ndarray
            The 3D point to transform

        Returns
        -------
        list
            2D coordinates [distance_along_section, elevation]
        """
        delta_x = q[0] - p0[0]
        delta_y = q[1] - p0[1]
        return [math.sqrt(delta_x**2 + delta_y**2), q[2]]

    matrix_gwb = []
    drillholes_line = {}
    springs_point = {}
    get_current_profiler().profile('hydro_setup')

    if drillhole_map:
        for d_id, line in drillhole_map.items():
            start_point = np.array(
                [line["start"]["x"], line["start"]["y"], line["start"]["z"]])
            end_point = np.array(
                [line["end"]["x"], line["end"]["y"], line["end"]["z"]])

            s_proj, s_valid = _proj_point_on_plane(start_point)
            e_proj, e_valid = _proj_point_on_plane(end_point)

            if s_valid or e_valid:
                drillholes_line[d_id] = [s_proj, e_proj]
    get_current_profiler().profile('hydro_project_drillholes')

    if spring_map:
        for s_id, p in spring_map.items():
            point = np.array([p["x"], p["y"], p["z"]])
            p_proj, valid = _proj_point_on_plane(point)
            if valid:
                springs_point[s_id] = p_proj
    get_current_profiler().profile('hydro_project_springs')

    points_polydata = pv.PolyData(xyz)
    # Test each point of the cross section against groundwater body meshes
    for gwb_id, meshes in gwb_meshes.items():
        gwb_id_int = int(gwb_id)
        for data in meshes:
            mesh = read_mesh_to_polydata(data)
            inside_points = points_polydata.select_enclosed_points(
                mesh, tolerance=0.00001)
            selected_points = inside_points["SelectedPoints"].astype(np.uint16)
            matrix_gwb.append(selected_points * gwb_id_int)
    get_current_profiler().profile('hydro_test_inside_gwbs')

    # Combine all gwb values into one matrix
    matrix_gwb_combine = []
    if matrix_gwb:
        # Stack matrices into a 2D array where each column is a GWB matrix
        stacked = np.column_stack(matrix_gwb) if len(
            matrix_gwb) > 1 else matrix_gwb[0]

        if len(matrix_gwb) > 1:
            nonzero_mask = stacked > 0
            row_has_nonzero = np.any(nonzero_mask, axis=1)
            # Cast to int from int8 to be able to serialize in json
            result = np.zeros(len(matrix_gwb[0]), dtype=np.int32)

            for i in np.where(row_has_nonzero)[0]:
                first_nonzero_idx = np.argmax(nonzero_mask[i])
                result[i] = stacked[i, first_nonzero_idx]

            matrix_gwb_combine = result.tolist()
        else:
            matrix_gwb_combine = stacked.astype(np.int32).tolist()

    get_current_profiler().profile('hydro_combine_gwbs')
    return drillholes_line, springs_point, matrix_gwb_combine
