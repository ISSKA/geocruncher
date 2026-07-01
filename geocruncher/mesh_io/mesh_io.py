import numpy as np
import pyvista as pv

from .draco import generate_draco, read_draco
from .off import generate_off, read_off
from .triangle_mesh import TriangleMesh


def is_off_file(data: bytes) -> bool:
    """Check if the bytes start with 'OFF' (ASCII) without full decode."""
    return len(data) >= 3 and data[:3] == b"OFF"


def generate_mesh(
    verts: np.ndarray | list, faces: np.ndarray | list, use_off=False
) -> bytes:
    if use_off:
        return generate_off(verts, faces).encode("utf-8")
    else:
        return generate_draco(verts, faces)


def read_mesh(data: bytes) -> TriangleMesh:
    """Read either OFF or Draco bytes and return a TriangleMesh."""
    if is_off_file(data):
        try:
            return read_off(data.decode("utf-8"))
        except Exception as e:
            raise ValueError("Invalid OFF file") from e
    else:
        try:
            return read_draco(data)
        except Exception as e:
            raise ValueError("Invalid Draco file") from e


def triangle_mesh_to_polydata(mesh: TriangleMesh) -> pv.PolyData:
    """Convert a TriangleMesh to a PyVista PolyData.
    Replaces the per-format conversion logic that was in read_draco_to_polydata."""
    points = np.asarray(mesh.vertices, dtype=np.float64)  # pyvista expects float64
    faces = np.asarray(mesh.triangles, dtype=np.int32)  # (M, 3)
    # PyVista face format: [3, v0, v1, v2, 3, v3, v4, v5, ...]
    faces_pv = np.hstack(
        [
            np.full((faces.shape[0], 1), 3, dtype=np.int32),
            faces,
        ]
    ).ravel()
    return pv.PolyData(points, faces=faces_pv)


def read_mesh_to_polydata(data: bytes) -> pv.PolyData:
    """Read either OFF or Draco bytes directly into a PyVista PolyData.
    Wrapper kept for backward compatibility with compute_intersections
    and voxel_computation — no changes needed in those callers."""
    return triangle_mesh_to_polydata(read_mesh(data))
