from dataclasses import dataclass

from numpy import ndarray


@dataclass
class TriangleMesh:
    vertices: ndarray  # (N, 3) float64
    triangles: ndarray  # (M, 3) int32
