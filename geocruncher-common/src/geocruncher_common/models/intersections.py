from typing import TypedDict

from geocruncher_common.models.common import Vec3Float, Line3D, Rectangle3D


class IntersectionsData(TypedDict):
    """Data given to the intersections computation"""
    # Optional. ID as string to 3D point
    springs: dict[str, Vec3Float]
    # Optional. ID as string to 3D line
    drillholes: dict[str, Line3D]
    resolution: int
    # cross sections, ID as string to lowerLeft - upperRight bounds. Could be replaced with Box
    toCompute: dict[str, Rectangle3D]
    computeMap: bool

class MeshIntersectionsResult(TypedDict):
    """Data returned by the mesh intersections computation"""
    forCrossSections: dict[str, list[list[int]]]
    drillholes: dict[str, dict[str, list[list[float]]]]
    springs: dict[str, dict[str, list[float]]]
    matrixGwb: dict[str, list[int]]
    # Optional
    forMaps: list[list[int]]


class FaultIntersectionsResult(TypedDict):
    """Data returned by the fault intersections computation"""
    # TODO: For standard intersections, Scala uses the int type, but for this one, the float (double) type. Find out why and make consistant
    forCrossSections: dict[str, dict[str, list[list[float]]]]
    # Optional
    forMaps: dict[str, list[list[float]]]


class IntersectionsResult(TypedDict):
    """Combined result of mesh and fault intersections computation"""
    mesh: MeshIntersectionsResult
    fault: FaultIntersectionsResult
