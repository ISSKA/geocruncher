# Based on https://github.com/ISSKA/pykarstnsim-demo/blob/main/src/pykarstnsim_demo/vkzipreader.py


import numpy as np

from geocruncher.generated_network.models import (
    GeneratedNetworkData,
    KarstNSimContent,
    StratigraphyInput,
    VoxelsUnitsInput,
)
from geocruncher.geometry import Vec2Float, Vec2Int, Vec3Int
from geocruncher.mesh_io.mesh_io import read_mesh


def load_voxels(voxels_lines: list[str]) -> np.ndarray:
    """Load voxel grid and return as ndarray of shape (nx, ny, nz, 2) where last dimension is (rank, gwb_id)"""
    # File has 3 lines:
    # format is:
    # XMIN=563987.601 XMAX=571512.301 YMIN=252987.602 YMAX=260512.302 ZMIN=0.0 ZMAX=1100.0 NUMBERX=200 NUMBERY=200 NUMBERZ=29 NOVALUE=0
    # rank gwb_id
    # ... ...
    if len(voxels_lines) < 3:
        raise ValueError("Voxel file must have at least 3 lines")

    # Parse the header
    header = voxels_lines[0]
    header_parts = header.split()
    if len(header_parts) != 10:
        raise ValueError("Malformed voxel header line (expected 10 tokens)")
    values = {part.split("=")[0]: float(part.split("=")[1]) for part in header_parts}
    try:
        nx = int(values["NUMBERX"])
        ny = int(values["NUMBERY"])
        nz = int(values["NUMBERZ"])
    except KeyError as e:
        raise ValueError(f"Missing key in voxel header: {e}")

    # Sanity check
    expected_n_voxels = nx * ny * nz
    actual_n_voxels = len(voxels_lines) - 2
    if expected_n_voxels != actual_n_voxels:
        raise ValueError(
            f"Voxel count mismatch: header says {expected_n_voxels}, but found {actual_n_voxels} data lines"
        )

    # Load the voxel data into an array of shape (n_voxels, 2)
    voxel_data = np.loadtxt(voxels_lines[2:], dtype=np.int32, ndmin=2)

    if voxel_data.shape != (expected_n_voxels, 2):
        raise ValueError(
            f"Expected {(expected_n_voxels, 2)} voxel table, got {voxel_data.shape}"
        )

    # File order is z -> y -> x (x changes fastest)
    # Reshape from (n_voxels, 2) to (nz, ny, nx, 2) and then transpose to (nx, ny, nz, 2)
    voxels = voxel_data.reshape(nz, ny, nx, 2).transpose(2, 1, 0, 3)
    return voxels


def build_karstnsim_content(
    data: GeneratedNetworkData,
    dem_bytes: bytes,
    voxels_str: str,
    fault_bytes: dict[int, bytes],
) -> KarstNSimContent:
    """Build a KarstNSimContent object from the given data and raw files."""

    # Load the DEM surface data
    surface_data = np.frombuffer(dem_bytes, dtype=np.float32)
    surface_data = surface_data.reshape(
        (data.dem_resolution["y"], data.dem_resolution["x"])
    )

    # Load and process the voxel grid
    voxels_lines = voxels_str.splitlines()
    voxels = load_voxels(voxels_lines)
    compute_resolution = Vec3Int(
        x=voxels.shape[0], y=voxels.shape[1], z=voxels.shape[2]
    )

    if surface_data.shape[0] < 2 or surface_data.shape[1] < 2:
        raise ValueError("Surface data grid must have at least 2 rows and 2 columns")

    # Resample the surface data to match the compute resolution
    y_step = max(1, data.dem_resolution["y"] // compute_resolution["y"])
    x_step = max(1, data.dem_resolution["x"] // compute_resolution["x"])

    surface_data = surface_data[::y_step, ::x_step]
    # Flip the surface data vertically to match
    surface_data = np.flipud(surface_data).copy()

    resampled_dem_resolution = Vec2Int(
        x=surface_data.shape[1],
        y=surface_data.shape[0],
    )

    # Compute the surface resolution in world units
    surface_resolution = Vec2Float(
        x=data.project_box.width / (surface_data.shape[1] - 1),
        y=data.project_box.height / (surface_data.shape[0] - 1),
    )

    # Load the faults
    faults = [read_mesh(bytes) for bytes in fault_bytes.values()]

    return KarstNSimContent(
        generation_params=data.generation_params,
        project_box=data.project_box,
        surface_data=surface_data,
        stratigraphy=StratigraphyInput(data.stratigraphy),
        compute_resolution=compute_resolution,
        voxels=voxels,
        voxels_units=VoxelsUnitsInput(data.voxels_units),
        faults=faults,
        springs=data.springs,
        gwbs=data.gwbs,
        surface_resolution=surface_resolution,
        resampled_dem_resolution=resampled_dem_resolution,
        is_base=data.is_base,
    )
