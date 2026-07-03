from enum import Enum
from typing import NotRequired, TypedDict

from geocruncher.geometry import Vec3Float, Vec3Int


class TunnelShape(str, Enum):
    """Possible shapes for tunnels"""

    CIRCLE = "Circle"
    RECTANGLE = "Rectangle"
    ELLIPTIC = "Elliptic"


class TunnelFunction(TypedDict):
    """Tunnel functions in all three dimensions"""

    x: str
    y: str
    z: str


class Tunnel(TypedDict):
    """Data defining a tunnel"""

    name: str
    shape: TunnelShape
    functions: list[TunnelFunction]
    radius: NotRequired[float | None]
    width: NotRequired[float | None]
    height: NotRequired[float | None]


class TunnelMeshesData(TypedDict):
    """Data given to the tunnel meshes computation"""

    tunnels: list[Tunnel]
    nb_vertices: int
    step: float
    idxStart: int
    idxEnd: int
    tStart: float
    tEnd: float


class BoxDict(TypedDict):
    """3D Box"""

    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float


class MeshesData(TypedDict):
    """Data given to the meshes computation"""

    resolution: Vec3Int
    box: NotRequired[BoxDict | None]


class MeshesResult(TypedDict):
    """Data returned by the meshes computation"""

    mesh: dict[str, bytes]
    fault: dict[str, bytes]


class IntersectionsData(TypedDict):
    """Data given to the intersections computation"""

    # ID as string to 3D point
    springs: NotRequired[dict[str, Vec3Float] | None]
    # ID as string to box
    drillholes: NotRequired[dict[str, BoxDict] | None]
    resolution: int
    # cross sections, ID as string to box for each segment
    toCompute: dict[str, list[BoxDict]]
    computeMap: bool


class MeshIntersectionsResult(TypedDict):
    """Data returned by the mesh intersections computation"""

    forCrossSections: dict[str, list[list[list[int]]]]
    drillholes: dict[str, list[dict[str, list[list[float]]]]]
    springs: dict[str, list[dict[str, list[float]]]]
    matrixGwb: dict[str, list[list[int]]]
    forMaps: NotRequired[list[list[int]]]


class FaultIntersectionsResult(TypedDict):
    """Data returned by the fault intersections computation"""

    # For Fault intersections, we return floats and not ints, as we return the distance from the fault in the potential field, whereas we returned the unit ID for the Meshes intersections
    forCrossSections: dict[str, list[dict[str, list[list[float]]]]]
    # Optional
    forMaps: dict[str, list[list[float]]]


class IntersectionsResult(TypedDict):
    """Combined result of mesh and fault intersections computation"""

    mesh: MeshIntersectionsResult
    fault: FaultIntersectionsResult


class Spring(TypedDict):
    """Spring data needed for the gwb meshes computation"""

    id: int
    location: Vec3Float
    unit_id: int


class UnitMesh(TypedDict):
    """UnitMesh"""

    unit_id: int
    mesh: str
