import numpy as np
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.native,
]

######## Tests ########


def test_draco_mesh_roundtrip_through_pyvista_preserves_topology_and_bounds():
    pytest.importorskip("DracoPy")
    pytest.importorskip("pyvista")
    mesh_io = pytest.importorskip("geocruncher.mesh_io.mesh_io")

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
