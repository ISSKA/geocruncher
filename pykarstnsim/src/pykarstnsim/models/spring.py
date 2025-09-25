from dataclasses import dataclass
from pathlib import Path

import pykarstnsim_core

from pykarstnsim.models.utils import parse_int_strict


@dataclass
class Spring:
    origin: pykarstnsim_core.Vector3
    index: int
    water_table_index: int
    radius: float = 0.0

    def __init__(
        self,
        origin: tuple[float, float, float],
        index: int,
        water_table_index: int,
        radius: float = 0.0,
    ):
        self.origin = pykarstnsim_core.Vector3(*origin)
        self.index = index
        self.water_table_index = water_table_index
        self.radius = radius

    @staticmethod
    def to_string(springs: list["Spring"]) -> str:
        lines = ["Index\tX\tYZ\tindex\tsurfindex\tradius"]
        for spring in springs:
            lines.append(
                f"{spring.index} {spring.origin.x} {spring.origin.y} {spring.origin.z} {spring.index} {spring.water_table_index} {spring.radius}"
            )
        return "\n".join(lines)

    @staticmethod
    def from_file(path: Path) -> list["Spring"]:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        # remove header line
        lines = lines[1:] if lines else []
        springs: list["Spring"] = []
        for line in lines:
            parts = line.split()
            if len(parts) < 7:
                raise ValueError(
                    f"Malformed spring line (expected at least 6 tokens): {line}"
                )
            try:
                index = int(parts[0])
                x = float(parts[1])
                y = float(parts[2])
                z = float(parts[3])
                index2 = parse_int_strict(parts[4])  # unused
                water_table_index = parse_int_strict(parts[5])
                radius = float(parts[6])
                springs.append(
                    Spring(
                        origin=(x, y, z),
                        index=index,
                        water_table_index=water_table_index,
                        radius=radius,
                    )
                )
            except ValueError as e:
                raise ValueError(f"Invalid spring line: {line}") from e

        return springs
