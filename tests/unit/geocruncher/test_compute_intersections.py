from types import SimpleNamespace
from typing import cast

import numpy as np
import pytest
from forgeo.gmlib.GeologicalModel3D import Box, GeologicalModel

import geocruncher.compute_intersections as intersections


def test_calculate_resolution_scales_larger_dimension_to_target():
    assert intersections.calculate_resolution(10, 5, 100) == (100, 50)
    assert intersections.calculate_resolution(4, 8, 50) == (25, 50)


def test_calculate_resolution_handles_zero_width_or_height():
    assert intersections.calculate_resolution(0, 8, 30) == (30, 30)
    assert intersections.calculate_resolution(8, 0, 30) == (30, 30)


def test_calculate_resolution_rejects_empty_dimensions():
    with pytest.raises(ValueError, match="can not be both 0"):
        intersections.calculate_resolution(0, 0, 30)


@pytest.mark.parametrize("width,height", [(-4, 8), (4, -8), (-4, -8)])
def test_calculate_resolution_rejects_negative_dimensions(width, height):
    with pytest.raises(ValueError, match="non-negative"):
        intersections.calculate_resolution(width, height, 50)


def test_compute_vertical_slice_points_for_sloped_slice():
    points = intersections.compute_vertical_slice_points(
        x_coord=(0, 2),
        y_coord=(0, 4),
        z_coord=(10, 20),
        resolution=(3, 2),
    )

    expected = np.array(
        [
            [0, 0, 10],
            [0, 0, 20],
            [1, 2, 10],
            [1, 2, 20],
            [2, 4, 10],
            [2, 4, 20],
        ],
        dtype=float,
    )
    np.testing.assert_allclose(points, expected)


def test_compute_vertical_slice_points_for_y_axis_aligned_slice():
    points = intersections.compute_vertical_slice_points(
        x_coord=(5, 5),
        y_coord=(-1, 1),
        z_coord=(0, 10),
        resolution=(3, 2),
    )

    expected = np.array(
        [
            [5, -1, 0],
            [5, -1, 10],
            [5, 0, 0],
            [5, 0, 10],
            [5, 1, 0],
            [5, 1, 10],
        ],
        dtype=float,
    )
    np.testing.assert_allclose(points, expected)


def test_compute_map_points_uses_model_topography_for_z_values():
    class Topography:
        @staticmethod
        def evaluate_z(xy):
            return xy[:, 0] * 10 + xy[:, 1]

    box = SimpleNamespace(xmin=0, xmax=2, ymin=10, ymax=12)
    model = SimpleNamespace(topography=Topography())

    points = intersections.compute_map_points(
        cast(Box, box), (3, 2), cast(GeologicalModel, model)
    )

    expected = np.array(
        [
            [0, 10, 10],
            [0, 12, 12],
            [1, 10, 20],
            [1, 12, 22],
            [2, 10, 30],
            [2, 12, 32],
        ],
        dtype=float,
    )
    np.testing.assert_allclose(points, expected)


def test_project_hydro_features_on_slice_projects_near_features_and_combines_gwbs(
    monkeypatch,
):
    class FakeBox:
        def __init__(self, xmin, ymin, zmin, xmax, ymax, zmax):
            self.xmin = xmin
            self.ymin = ymin
            self.zmin = zmin
            self.xmax = xmax
            self.ymax = ymax
            self.zmax = zmax

    mesh_selections = {
        "mesh-a": np.array([1, 0, 1], dtype=np.uint8),
        "mesh-b": np.array([0, 1, 1], dtype=np.uint8),
    }

    class FakePolyData:
        def __init__(self, points):
            self.points = points

        def select_enclosed_points(self, mesh, tolerance):
            assert tolerance == pytest.approx(0.00001)
            return {"SelectedPoints": mesh_selections[mesh]}

    read_calls = []

    def fake_read_mesh_to_polydata(data):
        read_calls.append(data)
        return data.decode("ascii")

    monkeypatch.setattr(intersections, "Box", FakeBox)
    monkeypatch.setattr(intersections.pv, "PolyData", FakePolyData)
    monkeypatch.setattr(
        intersections, "read_mesh_to_polydata", fake_read_mesh_to_polydata
    )

    drillholes, springs, gwb_matrix = intersections.project_hydro_features_on_slice(
        lower_left=np.array([0, 0, 0], dtype=float),
        upper_right=np.array([10, 0, 10], dtype=float),
        xyz=np.array([[1, 0, 0], [5, 0, 0], [9, 0, 0]], dtype=float),
        spring_map={
            "near": {"x": 5, "y": 0.2, "z": 3},
            "far": {"x": 5, "y": 1.0, "z": 3},
        },
        drillhole_map={
            "dh-1": {
                "xmin": 1,
                "ymin": 0.4,
                "zmin": 1,
                "xmax": 3,
                "ymax": 2.0,
                "zmax": 2,
            }
        },
        gwb_meshes={"7": [b"mesh-a"], "9": [b"mesh-b"]},
        max_dist_proj=0.5,
    )

    assert drillholes == {"dh-1": [[1.0, 1.0], [3.0, 2.0]]}
    assert springs == {"near": [5.0, 3.0]}
    assert gwb_matrix == [7, 9, 7]
    assert read_calls == [b"mesh-a", b"mesh-b"]
