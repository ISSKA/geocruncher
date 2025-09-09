import numpy as np
import pyvista as pv
import DracoPy

DRACO_COMPRESSION_LEVEL = 5
DRACO_QUANTIZATION_BITS = 14


def generate_draco(verts: np.array, faces: np.array) -> bytes:
    return DracoPy.encode(verts, faces,
                          quantization_bits=DRACO_QUANTIZATION_BITS,
                          compression_level=DRACO_COMPRESSION_LEVEL)


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
