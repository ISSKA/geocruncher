from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path


class ConnectivityType(IntEnum):
    NOT_CONNECTED = 0
    CONNECTED = 1
    UNCERTAIN = 2


@dataclass
class ConnectivityMatrix:
    # matrix of size (num_springs x num_sinks) with values from ConnectivityType
    matrix: list[list[ConnectivityType]]

    def to_string(self) -> str:
        lines = []
        for row in self.matrix:
            line = "\t".join(str(int(val)) for val in row)
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def from_file(path: Path) -> "ConnectivityMatrix":
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        matrix: list[list[ConnectivityType]] = []
        for line in lines:
            row: list[ConnectivityType] = []
            for val in line.split():
                try:
                    intval = int(val)
                    connectivity = ConnectivityType(intval)
                    row.append(connectivity)
                except ValueError:
                    raise ValueError(
                        f"Invalid connectivity matrix value: {val} in line: {line}"
                    )
            matrix.append(row)
        return ConnectivityMatrix(matrix=matrix)
