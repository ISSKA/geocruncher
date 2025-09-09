from enum import Enum
from typing import TypedDict


class TunnelShape(str, Enum):
    """Possible shapes for tunnels"""
    CIRCLE = 'Circle'
    RECTANGLE = 'Rectangle'
    ELLIPTIC = 'Elliptic'


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
    # Optional
    radius: float
    # Optional
    width: float
    # Optional
    height: float

class TunnelMeshesData(TypedDict):
    """Data given to the tunnel meshes computation"""
    tunnels: list[Tunnel]
    nb_vertices: int
    step: float
    idxStart: int
    idxEnd: int
    tStart: float
    tEnd: float
