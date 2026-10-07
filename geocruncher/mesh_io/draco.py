import DracoPy  # ty: ignore[unresolved-import]
import numpy as np

from .triangle_mesh import TriangleMesh

DRACO_COMPRESSION_LEVEL = 6
DRACO_QUANTIZATION_BITS = 14


def triangulate_faces(faces: np.ndarray | list) -> np.ndarray:
    """
    Convert mixed triangles, quads, and ngons to all triangles.
    Uses fan triangulation for ngons.

    Args:
        faces: np.array of faces, each being a list of vertex indices

    Returns:
        np.array of triangles with shape (N, 3)
    """
    triangles = []

    for face in faces:
        n_verts = len(face)

        if n_verts == 3:
            # Triangle - keep as is
            triangles.append(face)

        elif n_verts == 4:
            # Quad - split into two triangles
            triangles.append([face[0], face[1], face[2]])
            triangles.append([face[0], face[2], face[3]])

        elif n_verts >= 5:
            # Ngon - fan triangulation around first vertex
            # Creates triangles: (0,1,2), (0,2,3), (0,3,4), ...
            for i in range(1, n_verts - 1):
                triangles.append([face[0], face[i], face[i + 1]])

        else:
            raise ValueError(
                f"Invalid face with {n_verts} vertices (minimum 3 required)"
            )

    return np.array(triangles, dtype=np.int32)


def generate_draco(verts: np.ndarray | list, faces: np.ndarray | list) -> bytes:
    # numpy array have homogeneous shapes, so check if it is an numpy array of correct shape. otherwise assume not and triangulate
    f = (
        faces
        if isinstance(faces, np.ndarray) and faces.shape[1] == 3
        else triangulate_faces(faces)
    )
    return DracoPy.encode(
        verts,
        f,
        quantization_bits=DRACO_QUANTIZATION_BITS,
        compression_level=DRACO_COMPRESSION_LEVEL,
    )


def read_draco(draco_bytes: bytes) -> TriangleMesh:
    """Decode Draco bytes into a TriangleMesh."""

    data = DracoPy.decode_buffer_to_mesh(draco_bytes)
    if data.faces is None:
        raise ValueError("Draco mesh must contain triangular faces.")
    vertices = np.asarray(data.points, dtype=np.float64)  # (N, 3)
    triangles = np.asarray(data.faces, dtype=np.int32)  # (M, 3)
    return TriangleMesh(vertices=vertices, triangles=triangles)
