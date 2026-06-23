from types import SimpleNamespace
from typing import cast

import numpy as np
from forgeo.gmlib.GeologicalModel3D import GeologicalModel

import geocruncher.fault_intersections as fault_intersections


def _grid_points():
    return np.array([[x, y, 0.0] for x in (-1.0, 0.0, 1.0) for y in (-1.0, 0.0, 1.0)])


def _fault_data(*, stops_on=None, infinite=True, interface=None):
    return SimpleNamespace(
        stops_on=stops_on or [],
        infinite=infinite,
        potential_data=SimpleNamespace(
            interfaces=[
                np.array([interface or [0.0, 0.0, 0.0]], dtype=float),
            ]
        ),
    )


def test_compute_fault_intersections_clips_faults_against_stops_on_faults():
    grid_points = _grid_points()

    def major_fault(points):
        return points[:, 0]

    def minor_fault(points):
        return points[:, 1]

    model = SimpleNamespace(
        topography=SimpleNamespace(z=10.0),
        faults={
            "major": major_fault,
            "minor": minor_fault,
        },
        faults_data={
            "major": _fault_data(),
            "minor": _fault_data(stops_on=["major"], interface=[1.0, 0.0, 0.0]),
        },
        fault_ellipsoids={},
    )

    result = fault_intersections.compute_fault_intersections(
        grid_points, (3, 3), cast(GeologicalModel, model)
    )

    assert set(result) == {"major", "minor"}
    assert result["minor"] == [
        [None, None, -1.0],
        [None, None, 0.0],
        [None, None, 1.0],
    ]


def test_compute_fault_intersections_clips_finite_faults_against_ellipsoid():
    grid_points = _grid_points()

    def finite_fault(points):
        return points[:, 1]

    def ellipsoid(points):
        return np.where(points[:, 0] < 0, 1.0, -1.0)

    model = SimpleNamespace(
        topography=SimpleNamespace(z=10.0),
        faults={"finite": finite_fault},
        faults_data={"finite": _fault_data(infinite=False)},
        fault_ellipsoids={"finite": ellipsoid},
    )

    result = fault_intersections.compute_fault_intersections(
        grid_points, (3, 3), cast(GeologicalModel, model)
    )

    assert result == {
        "finite": [
            [None, -1.0, -1.0],
            [None, 0.0, 0.0],
            [None, 1.0, 1.0],
        ]
    }


def test_compute_fault_intersections_removes_faults_that_do_not_cross_slice():
    grid_points = _grid_points()

    def crossing_fault(points):
        return points[:, 1]

    def positive_fault(points):
        return points[:, 0] + 2.0

    model = SimpleNamespace(
        topography=SimpleNamespace(z=10.0),
        faults={
            "crossing": crossing_fault,
            "positive": positive_fault,
        },
        faults_data={
            "crossing": _fault_data(),
            "positive": _fault_data(),
        },
        fault_ellipsoids={},
    )

    result = fault_intersections.compute_fault_intersections(
        grid_points, (3, 3), cast(GeologicalModel, model)
    )

    assert result == {
        "crossing": [
            [-1.0, -1.0, -1.0],
            [0.0, 0.0, 0.0],
            [1.0, 1.0, 1.0],
        ]
    }
