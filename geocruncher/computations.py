"""
Geocruncher computation entry points and related type definitions
These functions take data as input and return data as output, with no Disk interaction
"""

import math
from enum import Enum
from typing import NotRequired, TypedDict, cast

import numpy as np
from forgeo.gmlib.GeologicalModel3D import Box, GeologicalModel

from geocruncher.profiler.profiler import start_step

from .compute_intersections import (
    calculate_resolution,
    compute_cross_section_ranks,
    compute_map_points,
    compute_vertical_slice_points,
    project_hydro_features_on_slice,
)
from .fault_intersections import compute_fault_intersections
from .geo_algo import GeoAlgo, GeoAlgoOutput
from .geological_model_input import deserialize_geological_model
from .gmlib_adapter import build_gmlib_project_data
from .mesh_generation import generate_faults_files, generate_volumes
from .profiler import (
    PROFILES,
    ProfilerMetadata,
    profile_step,
    set_profiler,
)
from .profiler.util import MetadataHelpers
from .tunnel_shape_generation import (
    get_circle_segment,
    get_elliptic_segment,
    get_rectangle_segment,
    tunnel_to_meshes,
)
from .voxel_computation import Voxels


class BoxDict(TypedDict):
    """3D Box"""

    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float


class Vec3Int(TypedDict):
    """3D Integer vector"""

    x: int
    y: int
    z: int


def _load_model(model_data: bytes, extent: BoxDict, dem: str) -> GeologicalModel:
    """Deserialize trusted protobuf input and construct the current gmlib model."""
    message = deserialize_geological_model(model_data)
    project_data = build_gmlib_project_data(
        message,
        extent,
        dem,
        validate_input=False,
    )
    return GeologicalModel(project_data, use_cache=False)


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


def compute_tunnel_meshes(
    data: TunnelMeshesData, metadata: ProfilerMetadata | None = None
) -> dict[str, bytes]:
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
    sub_t = 1.10 if data["idxStart"] != -1 and data["idxEnd"] != -1 else 1.0
    plane_segment = {
        TunnelShape.CIRCLE: lambda t: get_circle_segment(
            t["radius"] * sub_t, data["nb_vertices"]
        ),
        TunnelShape.RECTANGLE: lambda t: get_rectangle_segment(
            t["width"] * sub_t, t["height"] * sub_t, data["nb_vertices"]
        ),
        TunnelShape.ELLIPTIC: lambda t: get_elliptic_segment(
            t["width"] * sub_t, t["height"] * sub_t, data["nb_vertices"]
        ),
    }
    for tunnel in data["tunnels"]:
        # profile each tunnel separatly
        profiler = set_profiler(PROFILES["tunnel_meshes"])
        profiler.set_metadata("shape", tunnel["shape"]).set_metadata(
            "num_waypoints", len(tunnel["functions"]) + 1
        )
        profiler.update_metadata(metadata)

        output[tunnel["name"]] = tunnel_to_meshes(
            tunnel["functions"],
            data["step"],
            plane_segment[tunnel["shape"]](tunnel),
            data["idxStart"],
            data["tStart"],
            data["idxEnd"],
            data["tEnd"],
        )
        # write profiler result before moving on to the next tunnel
        profiler.save_results()
    return output


class MeshesData(TypedDict):
    """Data given to the meshes computation"""

    resolution: Vec3Int
    box: BoxDict


class MeshesResult(TypedDict):
    """Data returned by the meshes computation"""

    mesh: dict[str, bytes]
    fault: dict[str, bytes]


def compute_meshes(
    data: MeshesData,
    model_data: bytes,
    dem: str,
    metadata: ProfilerMetadata | None = None,
) -> MeshesResult:
    """Compute Unit and Fault Meshes.

    Parameters
    ----------
    data : MeshesData
        The configuration data.
    model_data : bytes
        Binary GeologicalModel protobuf.
    dem : str
        DEM datapoints as ASCIIGrid.
    metadata : dict, optional
        Optional metadata to include in profiler, such as project_id.

    Returns
    -------
    MeshesResult
        Dictionnary with mesh, a map from unit ID to OFF or Draco mesh file, and fault, a map from fault name to OFF or Draco mesh file.
    """
    profiler = set_profiler(PROFILES["meshes"])
    start_step("load_model")
    model = _load_model(model_data, data["box"], dem)

    shape = (data["resolution"]["x"], data["resolution"]["y"], data["resolution"]["z"])

    profiler.set_metadata(
        "num_erode_series", MetadataHelpers.num_erode_series(model)
    ).set_metadata(
        "num_onlap_series", MetadataHelpers.num_onlap_series(model)
    ).set_metadata("num_units", MetadataHelpers.num_units(model)).set_metadata(
        "num_finite_faults", MetadataHelpers.num_finite_faults(model)
    ).set_metadata(
        "num_infinite_faults", MetadataHelpers.num_infinite_faults(model)
    ).set_metadata(
        "num_stops_on_relations", MetadataHelpers.num_stops_on_relations(model)
    ).set_metadata(
        "num_contact_data", MetadataHelpers.num_contact_data(model)
    ).set_metadata("num_dips", MetadataHelpers.num_dips(model)).set_metadata(
        "resolution", shape[0] * shape[1] * shape[2]
    )
    profiler.update_metadata(metadata)

    profile_step("load_model")

    box = Box(**data["box"])
    output = cast(MeshesResult, generate_volumes(model, shape, box))
    profiler.save_results()
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

    # ID as string to 3D point
    springs: NotRequired[dict[str, Vec3Float] | None]
    # ID as string to box
    drillholes: NotRequired[dict[str, BoxDict] | None]
    resolution: int
    box: BoxDict
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


RATIO_MAX_DIST_PROJ = 0.2


def compute_intersections(
    data: IntersectionsData,
    model_data: bytes,
    dem: str,
    gwb_meshes: dict[str, list[bytes]],
    metadata: ProfilerMetadata | None = None,
) -> IntersectionsResult:
    """Compute Intersections.

    Parameters
    ----------
    data : IntersectionsData
        The configuration data.
    model_data : bytes
        Binary GeologicalModel protobuf.
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
    profiler = set_profiler(PROFILES["intersections"])
    start_step("load_model")
    model = _load_model(model_data, data["box"], dem)
    box = model.getbox()
    max_dist_proj = max(box.xmax - box.xmin, box.ymax - box.ymin) * RATIO_MAX_DIST_PROJ
    mesh_output: MeshIntersectionsResult = {
        "forCrossSections": {},
        "drillholes": {},
        "springs": {},
        "matrixGwb": {},
    }
    fault_output: FaultIntersectionsResult = {"forCrossSections": {}, "forMaps": {}}

    profiler.set_metadata(
        "num_erode_series", MetadataHelpers.num_erode_series(model)
    ).set_metadata(
        "num_onlap_series", MetadataHelpers.num_onlap_series(model)
    ).set_metadata("num_units", MetadataHelpers.num_units(model)).set_metadata(
        "num_finite_faults", MetadataHelpers.num_finite_faults(model)
    ).set_metadata(
        "num_infinite_faults", MetadataHelpers.num_infinite_faults(model)
    ).set_metadata(
        "num_stops_on_relations", MetadataHelpers.num_stops_on_relations(model)
    ).set_metadata(
        "num_contact_data", MetadataHelpers.num_contact_data(model, fault=False)
    ).set_metadata(
        "num_dips", MetadataHelpers.num_dips(model, fault=False)
    ).set_metadata("resolution", data["resolution"]).set_metadata(
        "num_sections", len(data["toCompute"])
    ).set_metadata("compute_map", data["computeMap"]).set_metadata(
        "num_springs", len(data.get("springs") or {})
    ).set_metadata("num_drillholes", len(data.get("drillholes") or {})).set_metadata(
        "num_gwb_parts", len(gwb_meshes)
    )
    profiler.update_metadata(metadata)

    has_hydro_layer = bool(data.get("springs") or data.get("drillholes") or gwb_meshes)

    profile_step("load_model")

    for key, intersection in data["toCompute"].items():
        # create empty arrays. each segment in the cross section gets it's data
        fault_output["forCrossSections"][key] = []
        mesh_output["forCrossSections"][key] = []
        mesh_output["drillholes"][key] = []
        mesh_output["springs"][key] = []
        mesh_output["matrixGwb"][key] = []

        for b in intersection:
            start_step("cross_section_grid")
            b = Box(**b)
            # FIXME: if we remove rounding, it breaks virtual drillhole slices. But it feels wrong to round, since we are rounding to arbitrary units of EPSG, usually meters, and the effect is not going to be the same on small and large projects
            x_coord = (round(b.xmin), round(b.xmax))
            y_coord = (round(b.ymin), round(b.ymax))
            z_coord = (round(b.zmin), round(b.zmax))
            x_extent = round(b.xmax) - round(b.xmin)
            y_extent = round(b.ymax) - round(b.ymin)
            height = round(b.zmax) - round(b.zmin)
            width = math.sqrt(x_extent**2 + y_extent**2)
            resolution = calculate_resolution(width, height, data["resolution"])
            xyz = compute_vertical_slice_points(x_coord, y_coord, z_coord, resolution)
            profile_step("cross_section_grid")

            mesh_output["forCrossSections"][key].append(
                compute_cross_section_ranks(xyz, resolution, model, topography=True)
            )
            if has_hydro_layer:
                lower_left = np.array([b.xmin, b.ymin, b.zmin])
                upper_right = np.array([b.xmax, b.ymax, b.zmax])

                # fix for drillholes slices where there is no x and y extent (fully vertical)
                if x_extent == 0 and y_extent == 0:
                    lower_left[0] -= 1
                    upper_right[0] += 1
                    lower_left[1] -= 1
                    upper_right[1] += 1

                d, s, m = project_hydro_features_on_slice(
                    lower_left,
                    upper_right,
                    xyz,
                    data.get("springs") or {},
                    data.get("drillholes") or {},
                    gwb_meshes,
                    max_dist_proj,
                )
                mesh_output["drillholes"][key].append(d)
                mesh_output["springs"][key].append(s)
                mesh_output["matrixGwb"][key].append(m)
            fault_output["forCrossSections"][key].append(
                compute_fault_intersections(xyz, resolution, model)
            )

    if data["computeMap"]:
        start_step("map_grid")
        width = box.xmax - box.xmin
        height = box.ymax - box.ymin
        resolution = calculate_resolution(width, height, data["resolution"])
        xyz = compute_map_points(box, resolution, model)
        profile_step("map_grid")

        mesh_output["forMaps"] = compute_cross_section_ranks(
            xyz, resolution, model, topography=False
        )
        fault_output["forMaps"] = compute_fault_intersections(xyz, resolution, model)
    profiler.save_results()
    return {"mesh": mesh_output, "fault": fault_output}


def compute_faults(
    data: MeshesData,
    model_data: bytes,
    dem: str,
    metadata: ProfilerMetadata | None = None,
) -> MeshesResult:
    """Compute Fault Meshes. Parameters and return types are the same as mesh computation.

    Parameters
    ----------
    data : MeshesData
        The configuration data.
    model_data : bytes
        Binary GeologicalModel protobuf.
    dem : str
        DEM datapoints as ASCIIGrid.
    metadata : dict, optional
        Optional metadata to include in profiler, such as project_id.

    Returns
    -------
    MeshesResult
        Dictionnary with mesh, an empty map, and fault, a map from fault name to OFF mesh file.
    """
    profiler = set_profiler(PROFILES["faults"])
    start_step("load_model")
    model = _load_model(model_data, data["box"], dem)

    shape = (data["resolution"]["x"], data["resolution"]["y"], data["resolution"]["z"])

    profiler.set_metadata(
        "num_finite_faults", MetadataHelpers.num_finite_faults(model)
    ).set_metadata(
        "num_infinite_faults", MetadataHelpers.num_infinite_faults(model)
    ).set_metadata(
        "num_stops_on_relations", MetadataHelpers.num_stops_on_relations(model)
    ).set_metadata(
        "num_contact_data", MetadataHelpers.num_contact_data(model, unit=False)
    ).set_metadata(
        "num_dips", MetadataHelpers.num_dips(model, unit=False)
    ).set_metadata("resolution", shape[0] * shape[1] * shape[2])
    profiler.update_metadata(metadata)

    profile_step("load_model")

    box = Box(**data["box"])

    output: MeshesResult = {
        "mesh": {},
        "fault": generate_faults_files(model, shape, box),
    }
    profiler.save_results()
    return output


def compute_voxels(
    data: MeshesData,
    model_data: bytes,
    dem: str,
    gwb_meshes: dict[str, list[bytes]],
    metadata: ProfilerMetadata | None = None,
) -> str:
    """Compute Voxels.

    Parameters
    ----------
    data : MeshesData
        The configuration data.
    model_data : bytes
        Binary GeologicalModel protobuf.
    dem : str
        DEM datapoints as ASCIIGrid.
    metadata : dict, optional
        Optional metadata to include in profiler, such as project_id.

    Returns
    -------
    str
        The VOX mesh file
    """
    profiler = set_profiler(PROFILES["voxels"])
    start_step("load_model")
    model = _load_model(model_data, data["box"], dem)

    shape = (data["resolution"]["x"], data["resolution"]["y"], data["resolution"]["z"])

    profiler.set_metadata(
        "num_erode_series", MetadataHelpers.num_erode_series(model)
    ).set_metadata(
        "num_onlap_series", MetadataHelpers.num_onlap_series(model)
    ).set_metadata("num_units", MetadataHelpers.num_units(model)).set_metadata(
        "num_gwb_parts", len(gwb_meshes)
    ).set_metadata("resolution", shape[0] * shape[1] * shape[2])
    profiler.update_metadata(metadata)

    profile_step("load_model")

    box = Box(**data["box"])

    output = Voxels.output(model, shape, box, gwb_meshes)
    profiler.save_results()
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


def compute_gwb_meshes(
    unit_meshes: dict[str, bytes],
    springs: list[Spring],
    metadata: ProfilerMetadata | None = None,
) -> GeoAlgoOutput:
    """Returns the metadata, then a dict of unit_id to OFF or Draco mesh file"""
    profiler = set_profiler(PROFILES["gwb_meshes"])

    profiler.set_metadata("num_units", len(unit_meshes)).set_metadata(
        "num_springs", len(springs)
    )
    profiler.update_metadata(metadata)

    results = GeoAlgo.output(unit_meshes, springs)
    profiler.save_results()
    return results
