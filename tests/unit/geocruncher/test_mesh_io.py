import numpy as np
import pytest
from meshio._exceptions import ReadError

import geocruncher.mesh_io.mesh_io as mesh_io
from geocruncher.mesh_io.draco import triangulate_faces
from geocruncher.mesh_io.mesh_io import is_off_file
from geocruncher.mesh_io.off import generate_off, read_off


def test_generate_off_and_read_off_roundtrip_triangular_mesh():
    vertices = np.array(
        [[0, 0, 0], [1.23456, 0, 0], [0, 1, 0]],
        dtype=float,
    )
    faces = [[0, 1, 2]]

    off = generate_off(vertices, faces, precision=2)
    mesh = read_off(off)

    np.testing.assert_allclose(
        mesh.vertices,
        np.array([[0, 0, 0], [1.23, 0, 0], [0, 1, 0]], dtype=float),
    )
    assert len(mesh.triangles) == 1
    assert mesh.triangles.shape[1] == 3
    np.testing.assert_array_equal(mesh.triangles[0], np.array([0, 1, 2]))


def test_read_off_ignores_blank_lines_and_comments_before_counts_and_vertices():
    off = "\n".join(
        [
            "OFF",
            "",
            "# counts follow",
            "3 1 0",
            "# vertices follow",
            "0 0 0",
            "1 0 0",
            "0 1 0",
            "3 0 1 2",
        ]
    )

    mesh = read_off(off)

    np.testing.assert_array_equal(mesh.triangles[0], np.array([0, 1, 2]))


def test_read_off_rejects_invalid_header():
    with pytest.raises(ReadError, match="Expected the first line"):
        read_off("NOFF\n0 0 0\n")


def test_read_off_rejects_non_triangular_faces():
    off = generate_off(
        verts=np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]),
        faces=[[0, 1, 2, 3]],
    )

    with pytest.raises(ReadError, match="triangular faces"):
        read_off(off)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"OFF\n", True),
        (b"OFF with extra bytes", True),
        (b"OF", False),
        (b"off\n", False),
        (b" NOFF", False),
    ],
)
def test_is_off_file_checks_binary_prefix(data, expected):
    assert is_off_file(data) is expected


def test_generate_mesh_returns_off_bytes_when_requested():
    mesh = mesh_io.generate_mesh(
        verts=np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]]),
        faces=[[0, 1, 2]],
        use_off=True,
    )

    assert isinstance(mesh, bytes)
    assert mesh.startswith(b"OFF\n3 1 0\n")


def test_generate_mesh_dispatches_to_draco_by_default(monkeypatch):
    def fake_generate_draco(verts, faces):
        np.testing.assert_array_equal(verts, np.array([[0, 0, 0]]))
        assert faces == [[0, 0, 0]]
        return b"draco"

    monkeypatch.setattr(mesh_io, "generate_draco", fake_generate_draco)

    assert mesh_io.generate_mesh(np.array([[0, 0, 0]]), [[0, 0, 0]]) == b"draco"


def test_read_mesh_reads_off_bytes(monkeypatch):
    sentinel_mesh = object()

    def fake_read_off(mesh):
        assert mesh.startswith("OFF\n")
        return sentinel_mesh

    monkeypatch.setattr(mesh_io, "read_off", fake_read_off)

    assert mesh_io.read_mesh(b"OFF\n0 0 0\n") is sentinel_mesh


def test_read_mesh_to_polydata_wraps_off_errors():
    with pytest.raises(ValueError, match="Invalid OFF file") as exc_info:
        mesh_io.read_mesh_to_polydata(b"OFF\nnot valid")

    assert exc_info.value.__cause__ is not None


def test_read_mesh_dispatches_draco_bytes(monkeypatch):
    sentinel_mesh = object()

    def fake_read_draco(data):
        assert data == b"not-off"
        return sentinel_mesh

    monkeypatch.setattr(mesh_io, "read_draco", fake_read_draco)

    assert mesh_io.read_mesh(b"not-off") is sentinel_mesh


def test_read_mesh_wraps_draco_errors(monkeypatch):
    def fake_read_draco(data):
        raise RuntimeError("decode failed")

    monkeypatch.setattr(mesh_io, "read_draco", fake_read_draco)

    with pytest.raises(ValueError, match="Invalid Draco file") as exc_info:
        mesh_io.read_mesh(b"not-off")

    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_triangulate_faces_keeps_triangles_unchanged():
    triangles = triangulate_faces([[0, 1, 2]])

    np.testing.assert_array_equal(triangles, np.array([[0, 1, 2]], dtype=np.int32))


def test_triangulate_faces_splits_quads():
    triangles = triangulate_faces([[0, 1, 2, 3]])

    np.testing.assert_array_equal(
        triangles,
        np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32),
    )


def test_triangulate_faces_fans_ngons():
    triangles = triangulate_faces([[0, 1, 2, 3, 4]])

    np.testing.assert_array_equal(
        triangles,
        np.array([[0, 1, 2], [0, 2, 3], [0, 3, 4]], dtype=np.int32),
    )


def test_triangulate_faces_rejects_invalid_faces():
    with pytest.raises(ValueError, match="minimum 3"):
        triangulate_faces([[0, 1]])
