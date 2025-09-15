from dataclasses import dataclass
from pathlib import Path

import pykarstnsim_core


@dataclass
class Surface:
    vertices: list[pykarstnsim_core.Vector3]
    triangles: list[pykarstnsim_core.Triangle]

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

        return Surface(vertices=vertices, triangles=triangles)

    def as_surface(self) -> pykarstnsim_core.Surface:
        return pykarstnsim_core.Surface(points=self.vertices, triangles=self.triangles)
