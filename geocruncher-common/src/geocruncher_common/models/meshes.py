from typing import TypedDict
from geocruncher_common.models.common import Vec3Int, BoxDict

class MeshesData(TypedDict):
    """Data given to the meshes computation"""
    resolution: Vec3Int
    # Optional
    box: BoxDict


class MeshesResult(TypedDict):
    """Data returned by the meshes computation"""
    mesh: dict[str, bytes]
    fault: dict[str, bytes]
