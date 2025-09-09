"""
    Geocruncher computation entry points and related type definitions
    These functions take data as input and return data as output, with no Disk interaction
"""

import math

import numpy as np
from geocruncher_common.models import (
    FaultIntersectionsResult,
    IntersectionsData,
    IntersectionsResult,
    MeshesData,
    MeshesResult,
    MeshIntersectionsResult,
    Spring,
    TunnelMeshesData,
    TunnelShape,
)
from gmlib.GeologicalModel3D import Box, GeologicalModel

from .ComputeIntersections import calculate_resolution, compute_cross_section_ranks, compute_map_points, compute_vertical_slice_points, project_hydro_features_on_slice
from .fault_intersections import compute_fault_intersections
from .geo_algo import GeoAlgo, GeoAlgoOutput
from .geomodeller_import import extract_project_data
from .MeshGeneration import generate_faults_files, generate_volumes
from .profiler import PROFILES, get_current_profiler, profile_step, set_profiler
from .profiler.util import MetadataHelpers
from .tunnel_shape_generation import get_circle_segment, get_elliptic_segment, get_rectangle_segment, tunnel_to_meshes
from .voxel_computation import Voxels


def compute_tunnel_meshes(data: TunnelMeshesData) -> dict[str, bytes]:
    """Compute Tunnel Meshes.

    Parameters
    ----------
    data : TunnelMeshesData
        The configuration data.

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
        get_current_profiler()\
            .set_metadata('shape', tunnel['shape'])\
            .set_metadata('num_waypoints', len(tunnel['functions']) + 1)
        output[tunnel['name']] = tunnel_to_meshes(tunnel['functions'], data['step'], plane_segment[tunnel['shape']](
            tunnel), data['idxStart'], data['tStart'], data['idxEnd'], data['tEnd'])
        # write profiler result before moving on to the next tunnel
        get_current_profiler().save_results()
    return output


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
        Dictionnary with mesh, a map from unit ID to OFF or Draco mesh file, and fault, a map from fault name to OFF or Draco mesh file.
    """
    set_profiler(PROFILES['meshes'])
    model = GeologicalModel(extract_project_data(xml, dem))

    shape = (data['resolution']['x'], data['resolution']
             ['y'], data['resolution']['z'])

    get_current_profiler()\
        .set_metadata('num_series', MetadataHelpers.num_series(model))\
        .set_metadata('num_units', MetadataHelpers.num_units(model))\
        .set_metadata('num_finite_faults', MetadataHelpers.num_finite_faults(model))\
        .set_metadata('num_infinite_faults', MetadataHelpers.num_infinite_faults(model))\
        .set_metadata('num_contact_data', MetadataHelpers.num_contact_data(model))\
        .set_metadata('num_dips', MetadataHelpers.num_dips(model))\
        .set_metadata('resolution', shape[0] * shape[1] * shape[2])\
    
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


RATIO_MAX_DIST_PROJ = 0.2


def compute_intersections(data: IntersectionsData, xml: str, dem: str, gwb_meshes: dict[str, list[bytes]]) -> IntersectionsResult:
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

    get_current_profiler()\
        .set_metadata('num_series', MetadataHelpers.num_series(model))\
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
        .set_metadata('num_gwb_parts', len(gwb_meshes))\

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
    set_profiler(PROFILES['faults'])
    model = GeologicalModel(extract_project_data(xml, dem))

    shape = (data['resolution']['x'], data['resolution']
             ['y'], data['resolution']['z'])

    get_current_profiler()\
        .set_metadata('num_finite_faults', MetadataHelpers.num_finite_faults(model))\
        .set_metadata('num_infinite_faults', MetadataHelpers.num_infinite_faults(model))\
        .set_metadata('num_contact_data', MetadataHelpers.num_contact_data(model, unit=False))\
        .set_metadata('num_dips', MetadataHelpers.num_dips(model, unit=False))\
        .set_metadata('resolution', shape[0] * shape[1] * shape[2])\

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


def compute_voxels(data: MeshesData, xml: str, dem: str, gwb_meshes: dict[str, list[bytes]]) -> str:
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
    set_profiler(PROFILES['voxels'])
    model = GeologicalModel(extract_project_data(xml, dem))

    shape = (data['resolution']['x'], data['resolution']
             ['y'], data['resolution']['z'])

    get_current_profiler()\
        .set_metadata('num_series', MetadataHelpers.num_series(model))\
        .set_metadata('num_units', MetadataHelpers.num_units(model))\
        .set_metadata('num_gwb_parts', len(gwb_meshes))\
        .set_metadata('resolution', shape[0] * shape[1] * shape[2])\

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


def compute_gwb_meshes(unit_meshes: dict[str, bytes], springs: list[Spring]) -> GeoAlgoOutput:
    """Returns the metadata, then a dict of unit_id to OFF or Draco mesh file"""
    set_profiler(PROFILES['gwb_meshes'])

    get_current_profiler()\
        .set_metadata('num_units', len(unit_meshes))\
        .set_metadata('num_springs', len(springs))

    results = GeoAlgo.output(unit_meshes, springs)
    get_current_profiler().save_results()
    return results
