"""
    Geocruncher computation entry points and related type definitions
    These functions take data as input and return data as output, with no Disk interaction
"""

import numpy as np
import math
from typing import TypedDict
from enum import Enum
from gmlib.GeologicalModel3D import GeologicalModel
from gmlib.GeologicalModel3D import Box

from .ComputeIntersections import compute_vertical_slice_points, project_hydro_features_on_slice, compute_map_points, compute_cross_section_ranks, calculate_resolution
from .fault_intersections import compute_fault_intersections
from .MeshGeneration import generate_volumes, generate_faults_files
from .geomodeller_import import extract_project_data
from .tunnel_shape_generation import get_circle_segment, get_elliptic_segment, get_rectangle_segment, tunnel_to_meshes
from .voxel_computation import Voxels
from .geo_algo import GeoAlgo, GeoAlgoOutput

from .profiler import PROFILES, set_profiler, get_current_profiler, profile_step
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


def compute_tunnel_meshes(data: TunnelMeshesData, metadata: dict = None) -> dict[str, bytes]:
    """Compute Tunnel Meshes.

    Parameters
    ----------
    data : TunnelMeshesData
        The configuration data.
    metadata : dict, optional
        Optional metadata to include in profiler, such as project_id.

    Returns
    -------
    dict[str, bytes]
        A map from Tunnel name to OFF or Draco mesh file.
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
        set_profiler(PROFILES['tunnel_meshes'])
        profiler = get_current_profiler()
        profiler.set_metadata('shape', tunnel['shape'])\
                .set_metadata('num_waypoints', len(tunnel['functions']) + 1) 
        if metadata:
            for key in metadata:
                profiler.set_metadata(key, metadata[key])
            
        output[tunnel['name']] = tunnel_to_meshes(tunnel['functions'], data['step'], plane_segment[tunnel['shape']](
            tunnel), data['idxStart'], data['tStart'], data['idxEnd'], data['tEnd'])
        # write profiler result before moving on to the next tunnel
        get_current_profiler().save_results()
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
    mesh: dict[str, bytes]
    fault: dict[str, bytes]


def compute_meshes(data: MeshesData, xml: str, dem: str, metadata: dict = None) -> MeshesResult:
    """Compute Unit and Fault Meshes.

    Parameters
    ----------
    data : MeshesData
        The configuration data.
    xml : str
        Project definition as Geomodeller XML.
    dem : str
        DEM datapoints as ASCIIGrid.
    metadata : dict, optional
        Optional metadata to include in profiler, such as project_id.

    Returns
    -------
    MeshesResult
        Dictionnary with mesh, a map from unit ID to OFF or Draco mesh file, and fault, a map from fault name to OFF or Draco mesh file.
    """
    set_profiler(PROFILES['meshes'])
    model = GeologicalModel(extract_project_data(xml, dem))

    shape = (data['resolution']['x'], data['resolution']
             ['y'], data['resolution']['z'])

    profiler = get_current_profiler()
    profiler.set_metadata('num_series', MetadataHelpers.num_series(model))\
        .set_metadata('num_units', MetadataHelpers.num_units(model))\
        .set_metadata('num_finite_faults', MetadataHelpers.num_finite_faults(model))\
        .set_metadata('num_infinite_faults', MetadataHelpers.num_infinite_faults(model))\
        .set_metadata('num_contact_data', MetadataHelpers.num_contact_data(model))\
        .set_metadata('num_dips', MetadataHelpers.num_dips(model))\
        .set_metadata('resolution', shape[0] * shape[1] * shape[2])
    if metadata:
        for key in metadata:
            profiler.set_metadata(key, metadata[key])

    profile_step('load_model')

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
    get_current_profiler().save_results()
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


def compute_intersections(data: IntersectionsData, xml: str, dem: str, gwb_meshes: dict[str, list[bytes]], metadata: dict = None) -> IntersectionsResult:
    """Compute Intersections.

    Parameters
    ----------
    data : IntersectionsData
        The configuration data.
    xml : str
        Project definition as Geomodeller XML.
    dem : str
        DEM datapoints as ASCIIGrid.
    gwb_meshes : dict[str, list[bytes]]
        A dict from GWB ID to meshes in the OFF or Draco format.
    metadata : dict, optional
        Optional metadata to include in profiler, such as project_id.

    Returns
    -------
    IntersectionsResult
        Results for cross sections, drillholes, sptrings, gwb matrix and maps.
        TODO: find a more complete explanation of what is returned and simplify return type.
    """
    set_profiler(PROFILES['intersections'])
    model = GeologicalModel(extract_project_data(xml, dem))
    box = model.getbox()
    cross_sections, drillhole_lines, spring_points, matrix_gwb = {}, {}, {}, {}
    fault_output: FaultIntersectionsResult = {
        'forCrossSections': {}, 'forMaps': {}}

    profiler = get_current_profiler()
    profiler.set_metadata('num_series', MetadataHelpers.num_series(model))\
        .set_metadata('num_units', MetadataHelpers.num_units(model))\
        .set_metadata('num_finite_faults', MetadataHelpers.num_finite_faults(model))\
        .set_metadata('num_infinite_faults', MetadataHelpers.num_infinite_faults(model))\
        .set_metadata('num_contact_data', MetadataHelpers.num_contact_data(model, fault=False))\
        .set_metadata('num_dips', MetadataHelpers.num_dips(model, fault=False))\
        .set_metadata('resolution', data['resolution'])\
        .set_metadata('num_sections', len(data['toCompute']))\
        .set_metadata('compute_map', data['computeMap'])\
        .set_metadata('num_springs', len(data['springs']) if 'springs' in data else 0)\
        .set_metadata('num_drillholes', len(data['drillholes']) if 'drillholes' in data else 0)\
        .set_metadata('num_gwb_parts', len(gwb_meshes))
    if metadata:
        for key in metadata:
            profiler.set_metadata(key, metadata[key])

    profile_step('load_model')

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
        x_extent = x_coord[1] - x_coord[0]
        y_extent = y_coord[1] - y_coord[0]
        width = math.sqrt(x_extent ** 2 + y_extent ** 2)
        height = abs(z_coord[1] - z_coord[0])
        resolution = calculate_resolution(width, height, data['resolution'])
        xyz = compute_vertical_slice_points(x_coord, y_coord, z_coord, resolution)
        profile_step('cross_section_grid')

        cross_sections[key] = compute_cross_section_ranks(xyz, resolution, model, topography=True)
        if any(key in data for key in ["springs", "drillholes"]) or gwb_meshes:
            lower_left = np.array([x_coord[0], y_coord[0], z_coord[0]])
            upper_right = np.array([x_coord[1], y_coord[1], z_coord[1]])

            # fix for drillholes slices where lower_left and upper_right are the same (except in z)
            if lower_left[0] == upper_right[0] and lower_left[1] == upper_right[1]:
                lower_left[0] -= 1
                upper_right[0] += 1
                lower_left[1] -= 1
                upper_right[1] += 1

            drillhole_lines[key], spring_points[key], matrix_gwb[key] = project_hydro_features_on_slice(
                                                                            lower_left, upper_right,
                                                                            xyz, data.get("springs"), data.get("drillholes"),
                                                                            gwb_meshes, max_dist_proj)
        fault_output['forCrossSections'][key] = compute_fault_intersections(xyz, resolution, model)

    mesh_output: MeshIntersectionsResult = {'forCrossSections': cross_sections,
                                            'drillholes': drillhole_lines, 'springs': spring_points, 'matrixGwb': matrix_gwb}
    if data['computeMap']:
        width = box.xmax - box.xmin
        height = box.ymax - box.ymin
        resolution = calculate_resolution(width, height, data['resolution'])
        xyz = compute_map_points(box, resolution, model)
        profile_step('map_grid')

        mesh_output['forMaps'] = compute_cross_section_ranks(xyz, resolution, model, topography=False)
        fault_output['forMaps'] = compute_fault_intersections(xyz, resolution, model)
    get_current_profiler().save_results()
    return {'mesh': mesh_output, 'fault': fault_output}


def compute_faults(data: MeshesData, xml: str, dem: str, metadata: dict = None) -> MeshesResult:
    """Compute Fault Meshes. Parameters and return types are the same as mesh computation.

    Parameters
    ----------
    data : MeshesData
        The configuration data.
    xml : str
        Project definition as Geomodeller XML.
    dem : str
        DEM datapoints as ASCIIGrid.
    metadata : dict, optional
        Optional metadata to include in profiler, such as project_id.

    Returns
    -------
    MeshesResult
        Dictionnary with mesh, an empty map, and fault, a map from fault name to OFF mesh file.
    """
    set_profiler(PROFILES['faults'])
    model = GeologicalModel(extract_project_data(xml, dem))

    shape = (data['resolution']['x'], data['resolution']
             ['y'], data['resolution']['z'])

    profiler = get_current_profiler()
    profiler.set_metadata('num_finite_faults', MetadataHelpers.num_finite_faults(model))\
        .set_metadata('num_infinite_faults', MetadataHelpers.num_infinite_faults(model))\
        .set_metadata('num_contact_data', MetadataHelpers.num_contact_data(model, unit=False))\
        .set_metadata('num_dips', MetadataHelpers.num_dips(model, unit=False))\
        .set_metadata('resolution', shape[0] * shape[1] * shape[2])
    if metadata:
        for key in metadata:
            profiler.set_metadata(key, metadata[key])

    profile_step('load_model')

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
    get_current_profiler().save_results()
    return output


def compute_voxels(data: MeshesData, xml: str, dem: str, gwb_meshes: dict[str, list[bytes]], metadata: dict = None) -> str:
    """Compute Voxels.

    Parameters
    ----------
    data : MeshesData
        The configuration data.
    xml : str
        Project definition as Geomodeller XML.
    dem : str
        DEM datapoints as ASCIIGrid.
    metadata : dict, optional
        Optional metadata to include in profiler, such as project_id.

    Returns
    -------
    str
        The VOX mesh file
    """
    set_profiler(PROFILES['voxels'])
    model = GeologicalModel(extract_project_data(xml, dem))

    shape = (data['resolution']['x'], data['resolution']
             ['y'], data['resolution']['z'])

    profiler = get_current_profiler()
    profiler.set_metadata('num_series', MetadataHelpers.num_series(model))\
        .set_metadata('num_units', MetadataHelpers.num_units(model))\
        .set_metadata('num_gwb_parts', len(gwb_meshes))\
        .set_metadata('resolution', shape[0] * shape[1] * shape[2])
    if metadata:
        for key in metadata:
            profiler.set_metadata(key, metadata[key])

    profile_step('load_model')

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
    get_current_profiler().save_results()
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



def compute_gwb_meshes(unit_meshes: dict[str, bytes], springs: list[Spring], metadata: dict = None) -> GeoAlgoOutput:
    """Returns the metadata, then a dict of unit_id to OFF or Draco mesh file"""
    set_profiler(PROFILES['gwb_meshes'])

    profiler = get_current_profiler()
    profiler.set_metadata('num_units', len(unit_meshes))\
        .set_metadata('num_springs', len(springs))
    if metadata:
        for key in metadata:
            profiler.set_metadata(key, metadata[key])

    results = GeoAlgo.output(unit_meshes, springs)
    get_current_profiler().save_results()
    return results
