from typing import TypedDict


class Vec2Int(TypedDict):
    """2D Integer vector"""

    x: int
    y: int


class Vec2Float(TypedDict):
    """2D Float vector"""

    x: float
    y: float


class Vec3Int(Vec2Int):
    """3D Integer vector"""

    z: int


class Vec3Float(Vec2Float):
    """3D Float vector"""

    z: float


class Rectangle3D(TypedDict):
    """Rectangle defined by its bounds. Could be replaced with Box"""

    lowerLeft: Vec3Float
    upperRight: Vec3Float


class Line3D(TypedDict):
    """Line defined by its start and end"""

    start: Vec3Float
    end: Vec3Float
