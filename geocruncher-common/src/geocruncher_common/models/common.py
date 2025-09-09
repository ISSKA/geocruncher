from typing import TypedDict


class BoxDict(TypedDict):
    """3D Box"""
    xMin: float
    yMin: float
    zMin: float
    xMax: float
    yMax: float
    zMax: float


class Vec3Int(TypedDict):
    """3D Integer vector"""
    x: int
    y: int
    z: int

class Vec3Float(TypedDict):
    """3D Float vector"""
    x: float
    y: float
    z: float

class Rectangle3D(TypedDict):
    """Rectangle defined by it's bounds. Could be replaced with Box"""
    lowerLeft: Vec3Float
    upperRight: Vec3Float


class Line3D(TypedDict):
    """Line defined by it's start and end"""
    start: Vec3Float
    end: Vec3Float
