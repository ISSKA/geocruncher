"""
    Geocruncher computation entry points and related type definitions
    These functions take data as input and return data as output, with no Disk interaction
"""

import numpy as np
from typing import TypedDict
from enum import Enum
from gmlib.GeologicalModel3D import GeologicalModel
from gmlib.GeologicalModel3D import Box

from .ComputeIntersections import compute_vertical_slice_points, project_hydro_features_on_slice, compute_map_points, compute_cross_section_ranks, compute_cross_section_fault_intersections
from .MeshGeneration import generate_volumes, generate_faults_files
from .geomodeller_import import extract_project_data
from .tunnel_shape_generation import get_circle_segment, get_elliptic_segment, get_rectangle_segment, tunnel_to_meshes
from .voxel_computation import Voxels
from .geo_algo import GeoAlgo

from .profiler.profiler import VkProfiler, PROFILES, set_current_profiler, get_current_profiler
from .profiler.util import MetadataHelpers


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


def compute_tunnel_meshes(data: TunnelMeshesData) -> dict[str, str]:
    """Compute Tunnel Meshes.

    Parameters
    ----------
    data : TunnelMeshesData
        The configuration data.

    Returns
    -------
    dict[str, str]
        A map from Tunnel name to OFF mesh file.
    """
    output = {}
    # sub tunnel are a bit bigger to wrap main tunnel
    sub_t = 1.10 if data['idxStart'] != -1 and data['idxEnd'] != -1 else 1.0
    plane_segment = {
        TunnelShape.CIRCLE: lambda t: get_circle_segment(t['radius'] * sub_t, data['nb_vertices']),
        TunnelShape.RECTANGLE: lambda t: get_rectangle_segment(t['width'] * sub_t, t['height'] * sub_t, data['nb_vertices']),
        TunnelShape.ELLIPTIC: lambda t: get_elliptic_segment(
            t['width'] * sub_t, t['height'] * sub_t, data['nb_vertices'])
    }
    for tunnel in data['tunnels']:
        # profile each tunnel separatly
        set_current_profiler(VkProfiler(PROFILES['tunnel_meshes']))
        get_current_profiler()\
            .set_profiler_metadata('shape', tunnel['shape'])\
            .set_profiler_metadata('num_waypoints', len(tunnel['functions']) + 1)
        output[tunnel['name']] = tunnel_to_meshes(tunnel['functions'], data['step'], plane_segment[tunnel['shape']](
            tunnel), data['idxStart'], data['tStart'], data['idxEnd'], data['tEnd'])
        # write profiler result before moving on to the next tunnel
        get_current_profiler().save_profiler_results()
    return output


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


class MeshesData(TypedDict):
    """Data given to the meshes computation"""
    resolution: Vec3Int
    # Optional
    box: BoxDict


class MeshesResult(TypedDict):
    """Data returned by the meshes computation"""
    mesh: dict[str, str]
    fault: dict[str, str]


def compute_meshes(data: MeshesData, xml: str, dem: str) -> MeshesResult:
    """Compute Unit and Fault Meshes.

    Parameters
    ----------
    data : MeshesData
        The configuration data.
    xml : str
        Project definition as Geomodeller XML.
    dem : str
        DEM datapoints as ASCIIGrid.

    Returns
    -------
    MeshesResult
        Dictionnary with mesh, a map from unit ID to OFF mesh file, and fault, a map from fault name to OFF mesh file.
    """
    set_current_profiler(VkProfiler(PROFILES['meshes']))
    model = GeologicalModel(extract_project_data(xml, dem))

    shape = (data['resolution']['x'], data['resolution']
             ['y'], data['resolution']['z'])

    get_current_profiler()\
        .set_profiler_metadata('num_series', MetadataHelpers.num_series(model))\
        .set_profiler_metadata('num_units', MetadataHelpers.num_units(model))\
        .set_profiler_metadata('num_finite_faults', MetadataHelpers.num_finite_faults(model))\
        .set_profiler_metadata('num_infinite_faults', MetadataHelpers.num_infinite_faults(model))\
        .set_profiler_metadata('num_interfaces', MetadataHelpers.num_interfaces(model))\
        .set_profiler_metadata('num_foliations', MetadataHelpers.num_foliations(model))\
        .set_profiler_metadata('resolution', shape[0] * shape[1] * shape[2])\
        .profile('load_model')

    if 'box' in data and data['box']:
        box = Box(xmin=data['box']['xMin'],
                  ymin=data['box']['yMin'],
                  zmin=data['box']['zMin'],
                  xmax=data['box']['xMax'],
                  ymax=data['box']['yMax'],
                  zmax=data['box']['zMax'])
    else:
        box = model.getbox()
    output = generate_volumes(model, shape, box)
    get_current_profiler().save_profiler_results()
    return output


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


RATIO_MAX_DIST_PROJ = 0.2


def compute_intersections(data: IntersectionsData, xml: str, dem: str, gwb_meshes: dict[str, list[str]]) -> IntersectionsResult:
    """Compute Intersections.

    Parameters
    ----------
    data : IntersectionsData
        The configuration data.
    xml : str
        Project definition as Geomodeller XML.
    dem : str
        DEM datapoints as ASCIIGrid.
    gwb_meshes : dict[str, list[str]]
        A dict from GWB ID to meshes in the OFF format.

    Returns
    -------
    IntersectionsResult
        Results for cross sections, drillholes, sptrings, gwb matrix and maps.
        TODO: find a more complete explanation of what is returned and simplify return type.
    """
    set_current_profiler(VkProfiler(PROFILES['intersections']))
    model = GeologicalModel(extract_project_data(xml, dem))
    box = model.getbox()
    cross_sections, drillhole_lines, spring_points, matrix_gwb = {}, {}, {}, {}
    fault_output: FaultIntersectionsResult = {
        'forCrossSections': {}, 'forMaps': {}}

    n_points = data['resolution']

    get_current_profiler()\
        .set_profiler_metadata('num_series', MetadataHelpers.num_series(model))\
        .set_profiler_metadata('num_units', MetadataHelpers.num_units(model))\
        .set_profiler_metadata('num_finite_faults', MetadataHelpers.num_finite_faults(model))\
        .set_profiler_metadata('num_infinite_faults', MetadataHelpers.num_infinite_faults(model))\
        .set_profiler_metadata('num_interfaces', MetadataHelpers.num_interfaces(model, fault=False))\
        .set_profiler_metadata('num_foliations', MetadataHelpers.num_foliations(model, fault=False))\
        .set_profiler_metadata('resolution', n_points)\
        .set_profiler_metadata('num_sections', len(data['toCompute']))\
        .set_profiler_metadata('compute_map', data['computeMap'])\
        .set_profiler_metadata('num_springs', len(data['springs']) if 'springs' in data else 0)\
        .set_profiler_metadata('num_drillholes', len(data['drillholes']) if 'drillholes' in data else 0)\
        .set_profiler_metadata('num_gwb_parts', sum(len(l) for l in gwb_meshes.values()))\
        .profile('load_model')

    for key, rect in data['toCompute'].items():
        # TODO: use this format directly to avoid converting
        x_coord = [int(round(rect['lowerLeft']['x'])),
                   int(round(rect['upperRight']['x']))]
        y_coord = [int(round(rect['lowerLeft']['y'])),
                   int(round(rect['upperRight']['y']))]
        z_coord = [int(round(rect['lowerLeft']['z'])),
                   int(round(rect['upperRight']['z']))]
        max_dist_proj = max(box.xmax - box.xmin, box.ymax -
                            box.ymin) * RATIO_MAX_DIST_PROJ
        xyz = compute_vertical_slice_points(x_coord, y_coord, z_coord, n_points)
        get_current_profiler().profile('cross_section_grid')

        cross_sections[key] = compute_cross_section_ranks(xyz, n_points, model, topography=True)
        if any(key in data for key in ["springs", "drillholes"]) or gwb_meshes:
            lower_left = np.array([x_coord[0], y_coord[0], z_coord[0]])
            upper_right = np.array([x_coord[1], y_coord[1], z_coord[1]])
            drillhole_lines[key], spring_points[key], matrix_gwb[key] = project_hydro_features_on_slice(
                                                                            lower_left, upper_right,
                                                                            xyz, data.get("springs"), data.get("drillholes"),
                                                                            gwb_meshes, max_dist_proj)
        fault_output['forCrossSections'][key] = compute_cross_section_fault_intersections(xyz, n_points, model)

    mesh_output: MeshIntersectionsResult = {'forCrossSections': cross_sections,
                                            'drillholes': drillhole_lines, 'springs': spring_points, 'matrixGwb': matrix_gwb}
    if data['computeMap']:
        xyz = compute_map_points(box, n_points, model)
        get_current_profiler().profile('map_grid')

        mesh_output['forMaps'] = compute_cross_section_ranks(xyz, n_points, model, topography=False)
        fault_output['forMaps'] = compute_cross_section_fault_intersections(xyz, n_points, model)
    get_current_profiler().save_profiler_results()
    return {'mesh': mesh_output, 'fault': fault_output}


def compute_faults(data: MeshesData, xml: str, dem: str) -> MeshesResult:
    """Compute Fault Meshes. Parameters and return types are the same as mesh computation.

    Parameters
    ----------
    data : MeshesData
        The configuration data.
    xml : str
        Project definition as Geomodeller XML.
    dem : str
        DEM datapoints as ASCIIGrid.

    Returns
    -------
    MeshesResult
        Dictionnary with mesh, an empty map, and fault, a map from fault name to OFF mesh file.
    """
    set_current_profiler(VkProfiler(PROFILES['faults']))
    model = GeologicalModel(extract_project_data(xml, dem))

    shape = (data['resolution']['x'], data['resolution']
             ['y'], data['resolution']['z'])

    get_current_profiler()\
        .set_profiler_metadata('num_finite_faults', MetadataHelpers.num_finite_faults(model))\
        .set_profiler_metadata('num_infinite_faults', MetadataHelpers.num_infinite_faults(model))\
        .set_profiler_metadata('num_interfaces', MetadataHelpers.num_interfaces(model, unit=False))\
        .set_profiler_metadata('num_foliations', MetadataHelpers.num_foliations(model, unit=False))\
        .set_profiler_metadata('resolution', shape[0] * shape[1] * shape[2])\
        .profile('load_model')

    if 'box' in data and data['box']:
        box = Box(xmin=data['box']['xMin'],
                  ymin=data['box']['yMin'],
                  zmin=data['box']['zMin'],
                  xmax=data['box']['xMax'],
                  ymax=data['box']['yMax'],
                  zmax=data['box']['zMax'])
    else:
        box = model.getbox()

    output = {'mesh': {}, 'fault': generate_faults_files(model, shape, box)}
    get_current_profiler().save_profiler_results()
    return output


def compute_voxels(data: MeshesData, xml: str, dem: str, gwb_meshes: dict[str, list[str]]) -> str:
    """Compute Voxels.

    Parameters
    ----------
    data : MeshesData
        The configuration data.
    xml : str
        Project definition as Geomodeller XML.
    dem : str
        DEM datapoints as ASCIIGrid.

    Returns
    -------
    str
        The VOX mesh file
    """
    set_current_profiler(VkProfiler(PROFILES['voxels']))
    model = GeologicalModel(extract_project_data(xml, dem))

    shape = (data['resolution']['x'], data['resolution']
             ['y'], data['resolution']['z'])

    get_current_profiler()\
        .set_profiler_metadata('num_series', MetadataHelpers.num_series(model))\
        .set_profiler_metadata('num_units', MetadataHelpers.num_units(model))\
        .set_profiler_metadata('num_gwb_parts', sum(len(l) for l in gwb_meshes.values()))\
        .set_profiler_metadata('resolution', shape[0] * shape[1] * shape[2])\
        .profile('load_model')

    if 'box' in data and data['box']:
        box = Box(xmin=data['box']['xMin'],
                  ymin=data['box']['yMin'],
                  zmin=data['box']['zMin'],
                  xmax=data['box']['xMax'],
                  ymax=data['box']['yMax'],
                  zmax=data['box']['zMax'])
    else:
        box = model.getbox()

    output = Voxels.output(model, shape, box, gwb_meshes)
    get_current_profiler().save_profiler_results()
    return output


class Spring(TypedDict):
    """Spring data needed for the gwb meshes computation"""
    id: int
    location: Vec3Float
    unit_id: int


class UnitMesh(TypedDict):
    """UnitMesh"""
    unit_id: int
    mesh: str


class GwbMeshesResult(TypedDict):
    """Data returned by the gwb meshes computation"""
    # OFF mesh file
    mesh: str
    # Geological Model Unit ID
    unit_id: int
    # Point of interest ID
    spring_id: int
    # Volume of the mesh
    volume: float


def compute_gwb_meshes(unit_meshes: dict[str, str], springs: list[Spring]) -> list[GwbMeshesResult]:
    set_current_profiler(VkProfiler(PROFILES['gwb_meshes']))

    get_current_profiler()\
        .set_profiler_metadata('num_units', len(unit_meshes))\
        .set_profiler_metadata('num_springs', len(springs))

    output = GeoAlgo.output(unit_meshes, springs)
    get_current_profiler().save_profiler_results()
    return output
