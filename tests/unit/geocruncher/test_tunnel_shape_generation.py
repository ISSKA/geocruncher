import math

import numpy as np
import pytest

import geocruncher.tunnel_shape_generation as tunnel


def test_get_circle_segment_returns_points_on_expected_circle():
    points = tunnel.get_circle_segment(radius=2, nb_vertices=8)

    assert len(points) == 8
    assert all(point[2] == 0 for point in points)
    distances = [np.linalg.norm(point[:2] - np.array([-2, 0])) for point in points]
    np.testing.assert_allclose(distances, np.full(8, 2.0), atol=1e-12)


def test_get_rectangle_segment_returns_evenly_distributed_corners():
    points = tunnel.get_rectangle_segment(width=4, height=2, nb_vertices=4)

    expected = np.array(
        [
            [0, 2, 0],
            [-2, 2, 0],
            [-2, -2, 0],
            [0, -2, 0],
        ],
        dtype=float,
    )
    np.testing.assert_allclose(points, expected)


def test_get_elliptic_segment_combines_floor_and_ellipse_points():
    width = 4
    height = 2
    points = tunnel.get_elliptic_segment(width=width, height=height, nb_vertices=12)

    assert len(points) == 12
    assert all(point[2] == 0 for point in points)

    linear_points = [point for point in points if point[0] == 0]
    assert linear_points[0][1] == pytest.approx(width / 2)
    assert linear_points[-1][1] <= linear_points[0][1]

    ellipse_points = [point for point in points if point[0] < 0]
    assert ellipse_points
    for point in ellipse_points:
        assert (point[0] / height) ** 2 + (point[1] / (width / 2)) ** 2 == (
            pytest.approx(1.0)
        )


def test_rotation_matrix_rotates_around_axis():
    matrix = tunnel._rotation_matrix(np.array([0, 0, 1]), math.pi / 2)

    np.testing.assert_allclose(
        matrix.dot(np.array([1, 0, 0])),
        np.array([0, 1, 0]),
        atol=1e-12,
    )


def test_connect_vertices_links_adjacent_series_and_wraps_around():
    triangles = tunnel._connect_vertices(nb_vertices=3, nb_serie=2)

    assert triangles == [
        [0, 3, 4],
        [1, 4, 5],
        [1, 0, 4],
        [2, 1, 5],
        [0, 2, 3],
        [2, 5, 3],
    ]


def test_project_points_offsets_points_when_normal_points_down():
    xy_points = [np.array([0, 0, 0]), np.array([0, 2, 0])]

    points = tunnel._project_points(
        normal=np.array([0, 0, -1]),
        bottom=np.array([10, 20, 30]),
        xy_points=xy_points,
    )

    assert points == [[10, 20, 30], [10, 22, 30]]


def test_tunnel_to_meshes_projects_vertices_and_delegates_mesh_generation(monkeypatch):
    captured = {}

    def fake_generate_mesh(vertices, triangles):
        captured["vertices"] = vertices
        captured["triangles"] = triangles
        return b"mesh"

    monkeypatch.setattr(tunnel, "generate_mesh", fake_generate_mesh)

    mesh = tunnel.tunnel_to_meshes(
        functions=[{"x": "0", "y": "0", "z": "-t"}],
        step=0.25,
        xy_points=[
            np.array([0, 0, 0]),
            np.array([0, 1, 0]),
            np.array([-1, 0, 0]),
        ],
        idxStart=0,
        tStart=0.25,
        idxEnd=0,
        tEnd=0.75,
    )

    assert mesh == b"mesh"
    np.testing.assert_allclose(
        captured["vertices"],
        np.array(
            [
                [0, 0, -0.25],
                [0, 1, -0.25],
                [-1, 0, -0.25],
                [0, 0, -0.5],
                [0, 1, -0.5],
                [-1, 0, -0.5],
            ],
            dtype=float,
        ),
    )
    np.testing.assert_array_equal(
        captured["triangles"],
        np.array(
            [
                [0, 3, 4],
                [1, 4, 5],
                [1, 0, 4],
                [2, 1, 5],
                [0, 2, 3],
                [2, 5, 3],
            ]
        ),
    )
