import numpy as np
import pyvista as pv
import DracoPy

DRACO_COMPRESSION_LEVEL = 6
DRACO_QUANTIZATION_BITS = 14


def triangulate_faces(faces: list) -> np.ndarray:
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


def read_draco_to_polydata(draco_bytes: bytes) -> pv.PolyData:
    # Decode Draco bytes (vertices + triangles)
    data = DracoPy.decode_buffer_to_mesh(draco_bytes)
    if data.faces is None:
        raise ValueError("Draco mesh must contain triangular faces.")

    # Convert to expected dtypes (float64 for points, int32 for faces)
    points = np.asarray(data.points, dtype=np.float64)  # shape (n_verts, 3)
    faces = np.asarray(data.faces, dtype=np.int32)      # shape (n_faces, 3)

    # PyVista expects faces as a 1D array formatted as [n_verts, v0, v1, ..., vN]
    # For triangles: [3, v0, v1, v2, 3, v3, v4, v5, ...]
    faces_pv = np.hstack([
        # Prefix each tri with "3"
        np.full((faces.shape[0], 1), 3, dtype=np.int32),
        faces
    ]).ravel()

    # Create PolyData directly
    mesh = pv.PolyData(points, faces=faces_pv)
    return mesh
