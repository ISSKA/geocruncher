from dataclasses import dataclass
from pathlib import Path

import pykarstnsim_core

from pykarstnsim.models.utils import parse_int_strict


@dataclass
class Sink:
    origin: pykarstnsim_core.Vector3
    index: int
    order: int
    radius: float = 0.0

    def __init__(
        self,
        origin: tuple[float, float, float],
        index: int,
        order: int,
        radius: float = 0.0,
    ):
        self.origin = pykarstnsim_core.Vector3(*origin)
        self.index = index
        self.order = order
        self.radius = radius

    @staticmethod
    def to_string(sinks: list["Sink"]) -> str:
        lines = ["Index\tX\tY\tZ\tindex\torder\tradius"]
        for sink in sinks:
            lines.append(
                f"{sink.index} {sink.origin.x} {sink.origin.y} {sink.origin.z} {sink.index} {sink.order} {sink.radius}"
            )
        return "\n".join(lines)

    @staticmethod
    def from_file(path: Path) -> list["Sink"]:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        # remove header line
        lines = lines[1:] if lines else []
        sinks: list["Sink"] = []
        for line in lines:
            parts = line.split()
            if len(parts) < 7:
                raise ValueError(
                    f"Malformed sink line (expected at least 6 tokens): {line}"
                )
            try:
                index = int(parts[0])
                x = float(parts[1])
                y = float(parts[2])
                z = float(parts[3])
                index2 = parse_int_strict(parts[4])  # unused
                order = parse_int_strict(parts[5])
                radius = float(parts[6])
                sinks.append(
                    Sink(
                        origin=(x, y, z),
                        index=index,
                        order=order,
                        radius=radius,
                    )
                )
            except ValueError as e:
                raise ValueError(f"Invalid sink line: {line}") from e

        return sinks
