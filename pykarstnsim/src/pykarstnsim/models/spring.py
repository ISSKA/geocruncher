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
                        origin=pykarstnsim_core.Vector3(x, y, z),
                        index=index,
                        water_table_index=water_table_index,
                        radius=radius,
                    )
                )
            except ValueError as e:
                raise ValueError(f"Invalid spring line: {line}") from e

        return springs
