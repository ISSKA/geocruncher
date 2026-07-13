# Based on https://github.com/ISSKA/pykarstnsim-demo/blob/main/src/pykarstnsim_demo/vkzipreader.py


import logging

import numpy as np

from geocruncher.geometry import Vec2Float, Vec2Int, Vec3Int
from geocruncher.karstnsim.models import (
    KarstNSimContent,
    KarstNSimData,
    KarstNSimStratigraphy,
    KarstNSimVoxelsHeader,
    KarstNSimVoxelsUnits,
)
from geocruncher.mesh_io.mesh_io import TriangleMesh, read_mesh

LOGGER = logging.getLogger(__name__)


def load_voxels(voxels_lines: list[str]) -> tuple[KarstNSimVoxelsHeader, np.ndarray]:
    """Load voxel grid and return as ndarray of shape (nx, ny, nz, 2) where last dimension is (rank, gwb_id)"""
    # file has 3 lines:
    # format is:
    # XMIN=563987.601 XMAX=571512.301 YMIN=252987.602 YMAX=260512.302 ZMIN=0.0 ZMAX=1100.0 NUMBERX=200 NUMBERY=200 NUMBERZ=29 NOVALUE=0
    # rank gwb_id
    # ... ...
    if len(voxels_lines) < 3:
        raise ValueError("Voxel file must have at least 3 lines")

    # parse the header
    header = voxels_lines[0]
    header_parts = header.split()
    if len(header_parts) != 10:
        raise ValueError("Malformed voxel header line (expected 10 tokens)")
    xmin, xmax, ymin, ymax, zmin, zmax, nx, ny, nz, novalue = map(
        float, [part.split("=")[1] for part in header_parts]
    )
    nx, ny, nz, novalue = int(nx), int(ny), int(nz), int(novalue)
    # sanity check
    expected_n_voxels = nx * ny * nz
    actual_n_voxels = len(voxels_lines) - 2
    if expected_n_voxels != actual_n_voxels:
        raise ValueError(
            f"Voxel count mismatch: header says {expected_n_voxels}, but found {actual_n_voxels} data lines"
        )
    header = KarstNSimVoxelsHeader(
        xmin=xmin,
        xmax=xmax,
        ymin=ymin,
        ymax=ymax,
        zmin=zmin,
        zmax=zmax,
        nx=nx,
        ny=ny,
        nz=nz,
        novalue=novalue,
    )
    LOGGER.info(f"Loaded voxel header: {header}")
    # create a ndarray of shape (nx, ny, nz, 2) filled with novalue
    # last dimension is (rank, gwb_id)
    voxels = np.full((nx, ny, nz, 2), novalue, dtype=np.int32)
    # parse the voxel data lines, they are in row-major order (x changes fastest)
    for z in range(nz):
        for y in range(ny):
            for x in range(nx):
                line_index = 2 + z * (ny * nx) + y * nx + x
                line = voxels_lines[line_index]
                parts = line.split()
                if len(parts) != 2:
                    raise ValueError(
                        f"Malformed voxel data line {line_index} (expected 2 tokens)"
                    )
                rank, gwb_id = map(int, parts)
                voxels[x, y, z, 0] = rank
                voxels[x, y, z, 1] = gwb_id
    LOGGER.info(f"Loaded voxel grid with shape {voxels.shape}")

    return (header, voxels)


def load_fault(fault_bytes: bytes) -> TriangleMesh:
    """Read a fault mesh from either OFF or Draco bytes into a TriangleMesh."""
    mesh = read_mesh(fault_bytes)
    LOGGER.info(
        "Loaded fault: %d vertices, %d triangles",
        len(mesh.vertices),
        len(mesh.triangles),
    )
    return mesh


def build_karstnsim_content(
    data: KarstNSimData,
    dem_bytes: bytes,
    voxels_str: str,
    fault_bytes: dict[int, bytes],
) -> KarstNSimContent:
    surface_data = np.frombuffer(dem_bytes, dtype=np.float32)
    surface_data = surface_data.reshape(
        (data["dem_resolution"]["y"], data["dem_resolution"]["x"])
    )
    voxels_lines = voxels_str.splitlines()
    voxels_header, voxels = load_voxels(voxels_lines)
    compute_resolution = Vec3Int(
        x=voxels_header.nx, y=voxels_header.ny, z=voxels_header.nz
    )

    # resample + flip: same arithmetic as read_zip
    surface_data = surface_data[
        :: data["dem_resolution"]["y"] // compute_resolution["y"],
        :: data["dem_resolution"]["x"] // compute_resolution["x"],
    ]
    surface_data = np.flipud(surface_data).copy()

    if surface_data.shape[0] < 2 or surface_data.shape[1] < 2:
        raise ValueError("Surface data grid must have at least 2 rows and 2 columns")

    surface_resolution = Vec2Float(
        x=data["project_box"].width / (surface_data.shape[1] - 1),
        y=data["project_box"].height / (surface_data.shape[0] - 1),
    )
    resampled_dem_resolution = Vec2Int(
        x=surface_data.shape[1],
        y=surface_data.shape[0],
    )
    faults = [load_fault(bytes) for bytes in fault_bytes.values()]

    return KarstNSimContent(
        simulation_params=data["simulation_params"],
        project_box=data["project_box"],
        dem_resolution=data["dem_resolution"],
        surface_data=surface_data,
        stratigraphy=KarstNSimStratigraphy(data["stratigraphy"]),
        compute_resolution=compute_resolution,
        voxels_header=voxels_header,
        voxels=voxels,
        voxels_units=KarstNSimVoxelsUnits(data["voxels_units"]),
        faults=faults,
        springs=data["springs"],
        gwbs=data["gwbs"],
        surface_resolution=surface_resolution,
        resampled_dem_resolution=resampled_dem_resolution,
    )
