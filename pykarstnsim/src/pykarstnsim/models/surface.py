from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pykarstnsim_core


@dataclass
class Surface:
    surface: pykarstnsim_core.Surface

    def to_string(self) -> str:
        return self.surface.to_string()

    @staticmethod
    def from_file(path: Path) -> "Surface":
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        vertices: list[pykarstnsim_core.Vector3] = []
        triangles: list[pykarstnsim_core.Triangle] = []

        if len(lines) < 2:
            raise ValueError("Surface file must have at least 2 lines")
        # skip header line
        lines = lines[1:]
        for line in lines:
            parts = line.split()
            if len(parts) < 5:
                raise ValueError(
                    f"Malformed surface line (expected at least 5 tokens): {line}"
                )
            try:
                type = parts[0]
                if type == "VRTX":
                    x = float(parts[2])
                    y = float(parts[3])
                    z = float(parts[4])
                    vertices.append(pykarstnsim_core.Vector3(x, y, z))
                elif type == "TRGL":
                    v1 = int(parts[2])
                    v2 = int(parts[3])
                    v3 = int(parts[4])
                    triangles.append(pykarstnsim_core.Triangle(v1, v2, v3))
                else:
                    raise ValueError(
                        f"Unknown surface line type: {type} in line: {line}"
                    )
            except ValueError as e:
                raise ValueError(f"Invalid surface line: {line}") from e

        surf = pykarstnsim_core.Surface(points=vertices, triangles=triangles)
        return Surface(surface=surf)

    @staticmethod
    def from_dem_grid(grid: np.ndarray, width: float, height: float) -> "Surface":
        """Create a plane mesh from a DEM grid, with origin at (0,0)"""
        n_rows, n_cols = grid.shape
        vertices: list[pykarstnsim_core.Vector3] = []
        triangles: list[pykarstnsim_core.Triangle] = []
        x_step = width / (n_cols - 1)
        y_step = height / (n_rows - 1)
        for i in range(n_rows):
            for j in range(n_cols):
                z = grid[i, j]
                vx = j * x_step
                vy = i * y_step
                vertices.append(pykarstnsim_core.Vector3(vx, vy, z))
        for i in range(n_rows - 1):
            for j in range(n_cols - 1):
                v1 = i * n_cols + j
                v2 = v1 + 1
                v3 = v1 + n_cols
                v4 = v3 + 1
                triangles.append(pykarstnsim_core.Triangle(v1, v2, v3))
                triangles.append(pykarstnsim_core.Triangle(v2, v4, v3))
        surf = pykarstnsim_core.Surface(points=vertices, triangles=triangles)
        return Surface(surface=surf)

    @staticmethod
    def from_vertices_and_triangles(
        vertices: np.ndarray, triangles: np.ndarray
    ) -> "Surface":
        """Create a Surface from numpy arrays of vertices and triangles"""
        surf = pykarstnsim_core.Surface.from_vertices_and_triangles(
            vertices=vertices, triangles=triangles
        )
        return Surface(surface=surf)
