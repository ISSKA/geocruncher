from typing import TypedDict
from geocruncher_common.models.common import Vec3Float


class Spring(TypedDict):
    """Spring data needed for the gwb meshes computation"""
    id: int
    location: Vec3Float
    unit_id: int
