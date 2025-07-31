from collections import defaultdict
import numpy as np
from gmlib.GeologicalModel3D import GeologicalModel
from .profiler.profiler import get_current_profiler

CLIP_VALUE = np.nan


class FaultIntersector:
    """Inspired by gmlib FaultTesselator"""

    def __init__(self, grid_points: np.ndarray, resolution: tuple[int, int], model: GeologicalModel):
        self._grid_points = grid_points
        self._resolution = resolution
        self._model = model
        self._topography = self._intersect_topography()

    def _sort_faults(self) -> list[str]:
        """
        Will sort faults from the most subordinated to the major ones.
        There is only a partial order relation between faults.
        """
        # find the faults that a given fault limits (reverse of stops on)
        fault_limits = defaultdict(set)
        for name, fault_data in self._model.faults_data.items():
            fault_limits[name].update(set())
            for limit in fault_data.stops_on:
                fault_limits[limit].add(name)
        sorted_faults = []
        faults = set(self._model.faults.keys())
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
        model = self._model

        if hasattr(model.topography, 'z') and isinstance(model.topography.z, float):
            # Horizontal plane case: potential = point.z - plane.z
            topography = self._grid_points[:, 2] - model.topography.z
        else:
            # Evaluate actual topography function
            topography = model.topography(self._grid_points)

        return topography

    def intersect(self) -> dict:
        res = self._resolution
        topography_2d = self._topography.reshape(res)

        model = self._model
        fault_potentials = {}

        # Evaluate all faults upfront
        for name, field in model.faults.items():
            fault_potentials[name] = field(self._grid_points).reshape(res)

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
                    E = ellipsoid(self._grid_points).reshape(res)
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
    resolution: tuple[int, int],
    model: GeologicalModel
) -> dict:
    """Compute fault intersections on a top-down or vertical geological cross section.

    Parameters
    ----------
    xyz : np.ndarray
        Array of 3D coordinates where fault values will be evaluated, shape (n_points^2, 3)
    resolution : tuple[int, int]
        x is the width resolution, y is the height resolution.
    model : gmlib.GeologicalModel3D.GeologicalModel
        GeologicalModel from gmlib containing the faults data

    Returns
    -------
    dict
        Dictionary mapping fault names to lists of intersection values,
        reshaped to resolution.

    Notes
    -----
    The order of the intersection values are transposed compared to the rank matrix. This is
    because VISKAR expects these values in transposed order.
    """
    intersector = FaultIntersector(grid_points, resolution, model)
    return intersector.intersect()
