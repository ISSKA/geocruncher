import pyvista as pv
import numpy as np

from .off import read_off, generate_off
from .draco import read_draco_to_polydata, generate_draco


def is_off_file(data: bytes) -> bool:
    """Check if the bytes start with 'OFF' (ASCII) without full decode."""
    return len(data) >= 3 and data[:3] == b"OFF"


def generate_mesh(verts: np.array, faces: np.array, use_off=False) -> bytes:
    if use_off:
        return generate_off(verts, faces)
    else:
        return generate_draco(verts, faces)


def read_mesh_to_polydata(data: bytes) -> pv.PolyData:
    """Load either OFF or Draco bytes into a PyVista PolyData."""
    if is_off_file(data):
        # Old OFF importer
        try:
            mesh_str = data.decode('utf-8')  # Decode only if confirmed OFF
            mesh = pv.from_meshio(read_off(mesh_str)).extract_geometry()
        except Exception as e:
            raise ValueError("Invalid OFF file") from e
    else:
        # Assume Draco (direct PolyData conversion)
        try:
            mesh = read_draco_to_polydata(data)
        except Exception as e:
            raise ValueError("Invalid Draco file") from e
    return mesh
