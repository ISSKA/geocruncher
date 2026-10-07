"""Data contracts shared by the API, task, and computation layers."""

import math
from enum import Enum
from typing import NotRequired, TypedDict

from geocruncher.geometry import Vec3Float, Vec3Int


class EvaluationExtent(TypedDict):
    """Project-space bounds for a 3D computation."""

    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float


class EvaluationExtentValidationError(ValueError):
    """Raised when a computation extent cannot define a valid 3D box."""


def validate_evaluation_extent(extent: EvaluationExtent) -> None:
    """Validate that every extent bound is finite and ordered."""
    bounds = (
        ("x", extent["xmin"], extent["xmax"]),
        ("y", extent["ymin"], extent["ymax"]),
        ("z", extent["zmin"], extent["zmax"]),
    )
    for axis, lower, upper in bounds:
        if not math.isfinite(lower) or not math.isfinite(upper):
            raise EvaluationExtentValidationError(
                f"box.{axis}min and box.{axis}max must be finite"
            )
        if lower >= upper:
            raise EvaluationExtentValidationError(
                f"box.{axis}min must be less than box.{axis}max"
            )


class TunnelShape(str, Enum):
    """Supported tunnel cross-section shapes."""

    CIRCLE = "Circle"
    RECTANGLE = "Rectangle"
    ELLIPTIC = "Elliptic"


class TunnelFunction(TypedDict):
    """Tunnel functions in all three dimensions."""

    x: str
    y: str
    z: str


class Tunnel(TypedDict):
    """Data defining a tunnel."""

    name: str
    shape: TunnelShape
    functions: list[TunnelFunction]
    radius: NotRequired[float | None]
    width: NotRequired[float | None]
    height: NotRequired[float | None]


class TunnelMeshesData(TypedDict):
    """Input for the tunnel-mesh computation."""

    tunnels: list[Tunnel]
    nb_vertices: int
    step: float
    idxStart: int
    idxEnd: int
    tStart: float
    tEnd: float


class MeshesData(TypedDict):
    """Input shared by mesh, fault, and voxel computations."""

    resolution: Vec3Int
    box: EvaluationExtent


class MeshesResult(TypedDict):
    """Result of the mesh and fault computations."""

    mesh: dict[str, bytes]
    fault: dict[str, bytes]


class IntersectionsData(TypedDict):
    """Input for the intersections computation."""

    springs: NotRequired[dict[str, Vec3Float] | None]
    drillholes: NotRequired[dict[str, EvaluationExtent] | None]
    resolution: int
    box: EvaluationExtent
    toCompute: dict[str, list[EvaluationExtent]]
    computeMap: bool


class MeshIntersectionsResult(TypedDict):
    """Mesh component of an intersections result."""

    forCrossSections: dict[str, list[list[list[int]]]]
    drillholes: dict[str, list[dict[str, list[list[float]]]]]
    springs: dict[str, list[dict[str, list[float]]]]
    matrixGwb: dict[str, list[list[int]]]
    forMaps: NotRequired[list[list[int]]]


class FaultIntersectionsResult(TypedDict):
    """Fault component of an intersections result."""

    forCrossSections: dict[str, list[dict[str, list[list[float]]]]]
    forMaps: dict[str, list[list[float]]]


class IntersectionsResult(TypedDict):
    """Combined mesh and fault intersections result."""

    mesh: MeshIntersectionsResult
    fault: FaultIntersectionsResult


class Spring(TypedDict):
    """Spring input for the groundwater-body mesh computation."""

    id: int
    location: Vec3Float
    unit_id: int


class GwbMeshesResult(TypedDict):
    """Metadata for one groundwater-body mesh result."""

    unit_id: int
    spring_id: int
    volume: float


class GeoAlgoOutput(TypedDict):
    """Groundwater-body mesh computation output."""

    metadata: list[GwbMeshesResult]
    meshes: list[bytes]
