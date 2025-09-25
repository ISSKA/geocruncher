from dataclasses import dataclass
from pathlib import Path

import pykarstnsim_core


@dataclass
class ProjectBox:
    basis: pykarstnsim_core.Vector3
    """origin of the project box"""
    u: pykarstnsim_core.Vector3
    """first axis of the project box (height)"""
    v: pykarstnsim_core.Vector3
    """second axis of the project box (width)"""
    w: pykarstnsim_core.Vector3
    """third axis of the project box (depth)"""
    cells_u: int
    cells_v: int
    cells_w: int
    density: list[float]
    """density of each cell in the project box (row-major order)"""
    karstification_potential: list[float]
    """karstification potential of each cell in the project box (row-major order)"""

    def __init__(
        self,
        basis: tuple[float, float, float],
        u: tuple[float, float, float],
        v: tuple[float, float, float],
        w: tuple[float, float, float],
        cells_u: int,
        cells_v: int,
        cells_w: int,
        density: list[float] = [],
        karstification_potential: list[float] = [],
    ):
        self.basis = pykarstnsim_core.Vector3(*basis)
        self.u = pykarstnsim_core.Vector3(*u)
        self.v = pykarstnsim_core.Vector3(*v)
        self.w = pykarstnsim_core.Vector3(*w)
        self.cells_u = cells_u
        self.cells_v = cells_v
        self.cells_w = cells_w
        expected_cells = cells_u * cells_v * cells_w
        if len(density) == 0:
            # each column is normalized to 1.0
            self.density = [1.0 / cells_u] * expected_cells
        else:
            if len(density) != expected_cells:
                raise ValueError(
                    f"Expected {expected_cells} density values, got {len(density)}"
                )
            self.density = density
        if len(karstification_potential) == 0:
            self.karstification_potential = [0.5] * expected_cells
        else:
            if len(karstification_potential) != expected_cells:
                raise ValueError(
                    f"Expected {expected_cells} karstification potential values, got {len(karstification_potential)}"
                )
            self.karstification_potential = karstification_potential

    def to_string(self) -> str:
        """Parameters
        number_properties	2
        basis	0	0	2.38419e-07
        u	0	0	590
        v	990	0	0
        w	0	790	0
        nu	80
        nv	100
        nw	60
        Index	density	karstif_potential
        ...
        """
        lines = []
        lines.append("Parameters")
        lines.append("number_properties\t2")
        lines.append(f"basis\t{self.basis.x}\t{self.basis.y}\t{self.basis.z}")
        lines.append(f"u\t{self.u.x}\t{self.u.y}\t{self.u.z}")
        lines.append(f"v\t{self.v.x}\t{self.v.y}\t{self.v.z}")
        lines.append(f"w\t{self.w.x}\t{self.w.y}\t{self.w.z}")
        lines.append(f"nu\t{self.cells_u}")
        lines.append(f"nv\t{self.cells_v}")
        lines.append(f"nw\t{self.cells_w}")
        lines.append("Index\tdensity\tkarstif_potential")
        for i in range(self.cells_u * self.cells_v * self.cells_w):
            lines.append(f"{i}\t{self.density[i]}\t{self.karstification_potential[i]}")

        return "\n".join(lines)

    @staticmethod
    def from_file(path: Path) -> "ProjectBox":
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if len(lines) < 10:
            raise ValueError("Project box file must have at least 10 lines")
        # skip two header lines
        lines = lines[2:]

        def _to_vec(line: str) -> tuple[float, float, float]:
            parts = line.split()
            if len(parts) != 4:
                raise ValueError(
                    f"Expected 4 values for vector, got {len(parts)}: {line}"
                )
            try:
                x = float(parts[1])
                y = float(parts[2])
                z = float(parts[3])
                return (x, y, z)
            except ValueError as e:
                raise ValueError(f"Invalid vector line: {line}") from e

        def _to_cell_count(line: str) -> int:
            try:
                parts = line.split()
                if len(parts) != 2:
                    raise ValueError(
                        f"Expected 2 values for cell count, got {len(parts)}: {line}"
                    )
                return int(parts[1])
            except ValueError as e:
                raise ValueError(f"Invalid cell count line: {line}") from e

        basis = _to_vec(lines[0])
        u = _to_vec(lines[1])
        v = _to_vec(lines[2])
        w = _to_vec(lines[3])
        try:
            cells_u = _to_cell_count(lines[4])
            cells_v = _to_cell_count(lines[5])
            cells_w = _to_cell_count(lines[6])
        except ValueError as e:
            raise ValueError(
                f"Invalid cell count line: {lines[4]}, {lines[5]}, {lines[6]}"
            ) from e
        # Read properties
        lines = lines[8:]
        density: list[float] = []
        karstification_potential: list[float] = []
        for line in lines:
            parts = line.split()
            if len(parts) < 3:
                raise ValueError(
                    f"Malformed property line (expected at least 3 tokens): {line}"
                )
            try:
                density.append(float(parts[1]))
                karstification_potential.append(float(parts[2]))
            except ValueError as e:
                raise ValueError(f"Invalid property line: {line}") from e
        expected_cells = cells_u * cells_v * cells_w
        if (
            len(density) != expected_cells
            or len(karstification_potential) != expected_cells
        ):
            raise ValueError(
                f"Expected {expected_cells} cells, got {len(density)} density and {len(karstification_potential)} karstification potential values"
            )

        return ProjectBox(
            basis=basis,
            u=u,
            v=v,
            w=w,
            cells_u=cells_u,
            cells_v=cells_v,
            cells_w=cells_w,
            density=density,
            karstification_potential=karstification_potential,
        )

    def as_box(self) -> pykarstnsim_core.Box:
        return pykarstnsim_core.Box(
            basis=self.basis,
            u=self.u,
            v=self.v,
            w=self.w,
            nu=self.cells_u,
            nv=self.cells_v,
            nw=self.cells_w,
        )
