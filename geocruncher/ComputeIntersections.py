import math

from typing import Tuple
import numpy as np
import pyvista as pv
from gmlib.GeologicalModel3D import GeologicalModel
from gmlib.architecture import from_GeoModeller, make_evaluator

from .profiler.profiler import get_current_profiler
from .off import read_off

class MapSlice:

    @staticmethod
    def output(xyz_reordered: np.array, n_points: int, model: GeologicalModel
    ) -> list:
        """Compute formation ranks for a top-down geological cross section.

        Parameters
        ----------
        xyz_reordered: np.array
            A numpy array of reordered (column by column -> x changes first, then y) coordinates, shape (n_points^2, 3).
        n_points: int
            Number of points in each dimension of the cross section.
        model: gmlib.GeologicalModel3D.GeologicalModel
            The GeologicalModel from gmlib to use for the formation rank evaluation.

        Returns:
            list: A list of ranks after evaluation, reshaped to (n_points, n_points).
        
        Notes
        -----
        The rank evaluation is being done without the topography, as it's not needed for a top-down view.
        """

        cppmodel = from_GeoModeller(model)
        evaluator = make_evaluator(cppmodel)

        is_base = model.pile.reference == 'base'
        rank_offset = -1 if is_base else 0

        ranks = evaluator(xyz_reordered) + rank_offset
        ranks.shape = (n_points, n_points)
        get_current_profiler().profile('map_ranks')
        return ranks.tolist()

class Slice:

    @staticmethod
    def compute_slice_points(
        x_coord: Tuple[int, int],
        y_coord: Tuple[int, int],
        z_slice_range: np.ndarray,
        n_points: int,
        is_on_y_axis: bool
    ) -> np.ndarray:
        """Calculate 3D points along a vertical slice plane.

        Parameters
        ----------
        x_coord : Tuple[int, int]
            Start and end x-coordinates of the slice line.
        y_coord : Tuple[int, int]
            Start and end y-coordinates of the slice line.
        z_slice_range : np.ndarray
            Array of z-coordinates defining the vertical range of the slice.
        n_points : int
            Number of points to generate along the slice line.
        is_on_y_axis : bool
            If True, the slice is parallel to the y-axis. If False, it's at an angle.

        Returns
        -------
        np.ndarray
            Array of shape (N, 3) containing the (x, y, z) coordinates of points
            in the slice plane, where N = n_points * len(z_slice_range).

        Notes
        -----
        For non-y-axis-aligned slices, points are computed using the slope between
        start and end coordinates. For y-axis-aligned slices, x remains constant
        while y varies linearly.
        """

        if not is_on_y_axis:
            x_slice_range = np.linspace(x_coord[0], x_coord[1], n_points)
            slope = (y_coord[0] - y_coord[1]) / (x_coord[0] - x_coord[1])
            z, x = np.meshgrid(z_slice_range, x_slice_range)
            y = slope * (x - x_coord[0]) + y_coord[0]
        else:
            y_slice_range = np.linspace(y_coord[0], y_coord[1], n_points)
            z, y = np.meshgrid(z_slice_range, y_slice_range)
            x = np.full_like(y, x_coord[0])
        xyz = np.stack((x.ravel(), y.ravel(), z.ravel()), axis=-1)
        return xyz

    @staticmethod
    def output(x_coord: Tuple[int, int],
               y_coord: Tuple[int, int],
               z_coord: Tuple[int, int],
               n_points: int,
               model: GeologicalModel,
               is_base: bool,
               data: dict,
               gwb_meshes: dict[str, list[str]],
               max_dist_proj: float
    ) -> Tuple[list, dict, dict, list]:
        """Compute vertical cross section by evaluating formation ranks and projecting
        hydrogeological features onto the section plane.

        Parameters
        ----------
        x_coord : Tuple[int, int]
            X-axis coordinates (start, end) of the section
        y_coord : Tuple[int, int]
            Y-axis coordinates (start, end) of the section
        z_coord : Tuple[int, int]
            Z-axis coordinates (start, end) of the section
        n_points : int
            Number of points to compute along each axis
        model : gmlib.GeologicalModel3D.GeologicalModel
            The GeologicalModel from gmlib to use for the formation rank evaluation.
        is_base : bool
            Flag indicating if this is a base section (affects rank calculation)
        data : dict
            Dictionary containing optional 'springs' and 'drillholes' data
        gwb_meshes : dict[str, list[str]]
            Dictionary mapping groundwater bodies to mesh elements
        max_dist_proj : float
            Maximum projection distance for hydrogeological features

        Returns
        -------
        ranks : list
            2D array of computed formation ranks
        drill_holes_line : dict
            Projected drill holes data
        springs_point : dict
            Projected springs data
        matrix_gwb : list
            Groundwater bodies mesh data
        """
        
        z_slice_range = np.linspace(z_coord[0], z_coord[1], n_points)

        is_on_y_axis = x_coord[0] == x_coord[1]
        drill_holes_line, springs_point, matrix_gwb = {}, {}, []

        xyz = Slice.compute_slice_points(x_coord, y_coord, z_slice_range, n_points, is_on_y_axis)

        if any(key in data for key in ["springs", "drillholes"]) or gwb_meshes:
            lower_left = np.array([x_coord[0], y_coord[0], z_coord[0]])
            upper_right = np.array([x_coord[1], y_coord[1], z_coord[1]])
            drill_holes_line, springs_point, matrix_gwb = Slice.ouput_hydro_layer(
                lower_left, upper_right, xyz,
                data.get("springs"), data.get("drillholes"),
                gwb_meshes, max_dist_proj
            )

        cppmodel = from_GeoModeller(model)
        topography = model.implicit_topography()
        evaluator = make_evaluator(cppmodel, topography)
       
        rank_offset = -1 if is_base else 0
        ranks = evaluator(xyz) + rank_offset
        ranks.shape = (n_points, n_points)
        get_current_profiler().profile('sections_ranks')
        return ranks.tolist(), drill_holes_line, springs_point, matrix_gwb

    @staticmethod
    def ouput_hydro_layer(
        lower_left: np.ndarray,
        upper_right: np.ndarray,
        xyz: np.ndarray,
        spring_map: dict,
        drill_hole_map: dict,
        gwb_meshes: dict[str, list[str]],
        max_dist_proj: float
    ) -> Tuple[dict, dict, list]:
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
        drill_hole_map : dict
            Dictionary of drill hole data with start and end coordinates
        gwb_meshes : dict[str, list[str]]
            Dictionary containing groundwater body IDs and their corresponding mesh strings in OFF format
        max_dist_proj : float
            Maximum projection distance for features

        Returns
        -------
        drill_holes_line : dict
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
        
        def proj_point_on_plane(q: np.ndarray) -> Tuple[list, bool]:
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
            return transform_value(q_proj), valid
        
        def transform_value(q: np.ndarray) -> list:
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
        drill_holes_line = {}
        springs_point = {}
        get_current_profiler().profile('hydro_setup')
        
        if drill_hole_map:
            for d_id, line in drill_hole_map.items():
                start_point = np.array([line["start"]["x"], line["start"]["y"], line["start"]["z"]])
                end_point = np.array([line["end"]["x"], line["end"]["y"], line["end"]["z"]])
                
                s_proj, s_valid = proj_point_on_plane(start_point)
                e_proj, e_valid = proj_point_on_plane(end_point)
                
                if s_valid or e_valid:
                    drill_holes_line[d_id] = [s_proj, e_proj]
        get_current_profiler().profile('hydro_project_drillholes')
        
        if spring_map:
            for s_id, p in spring_map.items():
                point = np.array([p["x"], p["y"], p["z"]])
                p_proj, valid = proj_point_on_plane(point)
                if valid:
                    springs_point[s_id] = p_proj
        get_current_profiler().profile('hydro_project_springs')
        
        points_polydata = pv.PolyData(xyz)
        # Test each point of the cross section against groundwater body meshes
        for gwb_id, meshes in gwb_meshes.items():
            gwb_id_int = int(gwb_id)
            for mesh_str in meshes:
                mesh = pv.from_meshio(read_off(mesh_str)).extract_geometry()
                inside_points = points_polydata.select_enclosed_points(mesh, tolerance=0.00001)
                selected_points = inside_points["SelectedPoints"].astype(np.uint16)
                matrix_gwb.append(selected_points * gwb_id_int)
        get_current_profiler().profile('hydro_test_inside_gwbs')
        
        # Combine all gwb values into one matrix
        matrix_gwb_combine = []
        if matrix_gwb:
            # Stack matrices into a 2D array where each column is a GWB matrix
            stacked = np.column_stack(matrix_gwb) if len(matrix_gwb) > 1 else matrix_gwb[0]
            
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
        return drill_holes_line, springs_point, matrix_gwb_combine


class FaultIntersection:

    @staticmethod
    def create_vertical_grid(
        x_coord: Tuple[int, int],
        y_coord: Tuple[int, int],
        z_coord: Tuple[int, int],
        n_points: int
    ) -> np.ndarray:
        """Create a vertical grid of points in 3D space.

        Parameters
        ----------
        x_coord : Tuple[int, int]
            Min and max x coordinates (x_min, x_max)
        y_coord : Tuple[int, int]
            Min and max y coordinates (y_min, y_max)
        z_coord : Tuple[int, int]
            Min and max z coordinates (z_min, z_max)
        n_points : int
            Number of points along each dimension

        Returns
        -------
        np.ndarray
            Array of shape (n_points * n_points, 3) containing the grid points
        """
        x = np.linspace(x_coord[0], x_coord[1], n_points)
        y = np.linspace(y_coord[0], y_coord[1], n_points)
        z = np.linspace(z_coord[0], z_coord[1], n_points)
        
        xx, zz = np.meshgrid(x, z)
        yy = np.full_like(xx, y[:, np.newaxis]).T
        
        xyz = np.stack([xx, yy, zz], axis=-1)
        return xyz.reshape(-1, 3)

    @staticmethod
    def output(
        x_coord: Tuple[int, int],
        y_coord: Tuple[int, int],
        z_coord: Tuple[int, int],
        n_points: int,
        model: GeologicalModel
    ) -> dict:
        """Compute fault intersections on a vertical cross section.

        Parameters
        ----------
        x_coord : Tuple[int, int]
            Min and max x coordinates (x_min, x_max)
        y_coord : Tuple[int, int]
            Min and max y coordinates (y_min, y_max)
        z_coord : Tuple[int, int]
            Min and max z coordinates (z_min, z_max)
        n_points : int
            Number of points along each dimension
        model : gmlib.GeologicalModel3D.GeologicalModel
            GeologicalModel from gmlib containing the faults data

        Returns
        -------
        dict
            Dictionary mapping fault names to 2D arrays of intersection values,
            where each array has shape (n_points, n_points)
        """
        xyz = FaultIntersection.create_vertical_grid(
            x_coord, y_coord, z_coord, n_points)
        get_current_profiler().profile('fault_sections_grid')
        output = {}
        for name, fault in model.faults.items():
            colored_points = fault(xyz)
            output[name] = colored_points.reshape(n_points, n_points).tolist()
        get_current_profiler().profile('fault_sections_tesselate')
        return output


class MapFaultIntersection:

    @staticmethod
    def output(xyz: np.array, n_points: int, model: GeologicalModel
    ) -> dict:
        """Compute fault intersections on a top-down geological cross section.

        Parameters
        ----------
        xyz : np.array
            Array of 3D coordinates where fault values will be evaluated, ordered row by row -> y changes first, then x, shape (n_points^2, 3)
        n_points : int
            Number of points in each dimension of the output grid
        model : gmlib.GeologicalModel3D.GeologicalModel
            GeologicalModel from gmlib containing the faults data

        Returns
        -------
        dict
            Dictionary mapping fault names to 2D arrays of intersection values,
            where each array has shape (n_points, n_points)
        """
        output = {}
        for name, fault in model.faults.items():
            colored_points = fault(xyz)
            output[name] = colored_points.reshape(n_points, n_points).tolist()
        get_current_profiler().profile('fault_map_tesselate')
        return output
