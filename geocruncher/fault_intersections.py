from collections import defaultdict
import numpy as np
from gmlib.GeologicalModel3D import GeologicalModel
from .profiler.profiler import get_current_profiler

CLIP_VALUE = np.nan


class FaultIntersector:
    """Inspired by gmlib FaultTesselator"""

    def __init__(self, grid_points, n_points, model):
        self.grid_points = grid_points
        self.n_points = n_points
        self.model = model
        self.topography = self._intersect_topography()

    def _sort_faults(self):
        """
        Will sort faults from the most subordinated to the major ones.
        There is only a partial order relation between faults.
        """
        # find the faults that a given fault limits (reverse of stops on)
        fault_limits = defaultdict(set)
        for name, fault_data in self.model.faults_data.items():
            fault_limits[name].update(set())
            for limit in fault_data.stops_on:
                fault_limits[limit].add(name)
        sorted_faults = []
        faults = set(self.model.faults.keys())
        while len(faults) > 0:
            subordinated_faults = set(
                fault for fault, limits in fault_limits.items() if len(limits) == 0
            )
            for limits in fault_limits.values():
                limits -= subordinated_faults
            for fault in subordinated_faults:
                fault_limits.pop(fault)
            sorted_faults.extend(subordinated_faults)
            faults -= subordinated_faults
        return sorted_faults

    def _intersect_topography(self):
        model = self.model

        if hasattr(model.topography, 'z') and isinstance(model.topography.z, float):
            # Horizontal plane case: potential = point.z - plane.z
            topography = self.grid_points[:, 2] - model.topography.z
        else:
            # Evaluate actual topography function
            topography = model.topography(self.grid_points)

        return topography

    def intersect(self):
        n = self.n_points
        topography_2d = self.topography.reshape(n, n)

        model = self.model
        fault_potentials = {}

        # Evaluate all faults upfront
        for name, field in model.faults.items():
            fault_potentials[name] = field(self.grid_points).reshape(n, n)

        # Process each fault in dependency order
        for name in self._sort_faults():
            fault_data = model.faults_data[name]
            potential = fault_potentials[name]

            # Skip empty fault potentials
            if not np.any(potential):
                continue

            points = fault_data.potential_data.interfaces[0]

            # 1. Clip against topography
            # Set above ground to None
            potential[topography_2d > 0] = CLIP_VALUE

            # 2. Clip against limiting faults
            for limit in fault_data.stops_on:
                if limit not in fault_potentials:
                    continue

                limiting_potential = fault_potentials[limit]
                if not np.any(limiting_potential):
                    continue

                # Determine valid side using mean potential
                limit_values = model.faults[limit](points)
                valid_side = np.mean(
                    limit_values) if limit_values.size > 0 else 1.0

                # Create mask for valid region (same sign)
                valid_mask = (valid_side * limiting_potential) > 0
                potential[~valid_mask] = CLIP_VALUE

            # 3. Clip finite faults
            if not fault_data.infinite:
                ellipsoid = model.fault_ellipsoids.get(name)
                if ellipsoid:
                    E = ellipsoid(self.grid_points).reshape(n, n)
                    if np.any(E):
                        # Set outside ellipsoid to None
                        potential[E > 0] = CLIP_VALUE

        # Prepare output: transpose and convert to list
        for name, potential in fault_potentials.items():
            transposed = np.transpose(potential)
            # Setting the values to None directly doesn't work, so we use np.nan and replace it all with None at the end
            fault_potentials[name] = np.where(
                np.isnan(transposed), None, transposed).tolist()

        get_current_profiler().profile('fault_cross_section_tesselate')
        return fault_potentials


def compute_fault_intersections(
    grid_points: np.ndarray,
    n_points: int,
    model: GeologicalModel
) -> dict:
    """Compute fault intersections on a top-down or vertical geological cross section.

    Parameters
    ----------
    xyz : np.ndarray
        Array of 3D coordinates where fault values will be evaluated, shape (n_points^2, 3)
    n_points : int
        Number of points in each dimension of the output grid
    model : gmlib.GeologicalModel3D.GeologicalModel
        GeologicalModel from gmlib containing the faults data

    Returns
    -------
    dict
        Dictionary mapping fault names to lists of intersection values,
        reshaped to (n_points, n_points).

    Notes
    -----
    The order of the intersection values are transposed compared to the rank matrix. This is
    because VISKAR expects these values in transposed order.
    """
    intersector = FaultIntersector(grid_points, n_points, model)
    return intersector.intersect()
