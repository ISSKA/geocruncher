"""
Defines a generic mesh made of triangles
Put in a separate file to avoid circular imports between mesh_io.py and off.py / draco.py
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class TriangleMesh:
    vertices: np.ndarray  # (N, 3) float64
    triangles: np.ndarray  # (M, 3) int32
