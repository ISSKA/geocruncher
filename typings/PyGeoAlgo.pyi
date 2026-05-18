from typing import Any

class Point_3:
    def __init__(self, x: float, y: float, z: float) -> None: ...

class Spring:
    id: int

    def __init__(self, id: int, location: Point_3, unit_id: int) -> None: ...

class UnitMesh:
    def __init__(self, mesh: Any, unit_id: int) -> None: ...

class FileIO:
    @staticmethod
    def load_from_bytes(data: bytes) -> Any: ...
    @staticmethod
    def write_to_bytes(mesh: Any) -> bytes: ...

class Aquifer:
    unit_id: int
    spring: Spring
    volume: float
    mesh: Any

class AquiferCalc:
    def __init__(self, meshes: list[UnitMesh], springs: list[Spring]) -> None: ...
    def calculate(self) -> list[Aquifer]: ...
