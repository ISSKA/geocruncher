import numpy as np
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.native,
]

######## Tests ########


def test_draco_mesh_roundtrip_through_pyvista_preserves_topology_and_bounds(mesh_io):
    pytest.importorskip("DracoPy")

    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=float,
    )
    faces = [
        [0, 1, 2, 3],
        [0, 1, 4],
    ]
    expected_triangles_after_wrapper_triangulation = 3

    encoded = mesh_io.generate_mesh(vertices, faces)
    decoded = mesh_io.read_mesh_to_polydata(encoded)
    # Draco/PyVista may duplicate or reorder vertices => compare stable coordinates.
    unique_points = np.unique(np.round(decoded.points, 6), axis=0)

    assert not mesh_io.is_off_file(encoded)
    np.testing.assert_allclose(
        unique_points,
        np.array(
            [
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 1.0],
                [0.0, 1.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
            ]
        ),
    )
    assert decoded.n_cells == expected_triangles_after_wrapper_triangulation
    np.testing.assert_allclose(decoded.bounds, (0, 1, 0, 1, 0, 1), atol=1e-3)


def test_off_mesh_bytes_read_to_pyvista_polydata_has_sane_bounds(
    fixture_bytes, mesh_io
):
    off = fixture_bytes("gwb_meshes/7.off")
    decoded = mesh_io.read_mesh_to_polydata(off)

    assert mesh_io.is_off_file(off)
    assert decoded.n_points == 8
    assert decoded.n_cells == 12
    np.testing.assert_allclose(
        decoded.bounds,
        (539000, 543000, 194000, 197000, -1000, 1500),
        atol=1e-6,
    )
