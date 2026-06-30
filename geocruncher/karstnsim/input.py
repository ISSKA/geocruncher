# Based on https://github.com/ISSKA/pykarstnsim-demo/blob/main/src/pykarstnsim_demo/vkzipreader.py


import logging
from dataclasses import dataclass

import numpy as np

from geocruncher.computations import KarstNSimData, Vec3Int
from geocruncher.karstnsim.models import (
    KarstNSimDemResolution,
    KarstNSimFault,
    KarstNSimGroundwaterBody,
    KarstNSimProjectBox,
    KarstNSimSpring,
    KarstNSimStratigraphy,
    KarstNSimVoxelsHeader,
    KarstNSimVoxelsUnits,
    Point2D,
    SimulationParameters,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class KarstNSimContent:
    """Replaces VkZipContent — holds all parsed simulation inputs"""

    simulation_params: SimulationParameters
    project_box: KarstNSimProjectBox
    dem_resolution: KarstNSimDemResolution
    surface_data: np.ndarray  # resampled, flipped, shape (ny, nx)
    stratigraphy: KarstNSimStratigraphy
    compute_resolution: Vec3Int
    voxels_header: KarstNSimVoxelsHeader
    voxels: np.ndarray  # shape (nx, ny, nz, 2)
    voxels_units: KarstNSimVoxelsUnits
    faults: list[KarstNSimFault]
    springs: list[KarstNSimSpring]
    gwbs: list[KarstNSimGroundwaterBody]
    surface_resolution: Point2D
    resampled_dem_resolution: KarstNSimDemResolution


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


def load_fault(fault_bytes: bytes) -> KarstNSimFault:
    # faults are packed as follows:
    # - int32: number of vertices (N)
    # - float32[3*N]: vertex positions (x1, y1, z1, x2, y2, z2, ..., xN, yN, zN)
    # - int32: number of triangles (M)
    # - int32[3*M]: triangle indices (i1_1, i1_2, i1_3, i2_1, i2_2, i2_3, ..., iM_1, iM_2, iM_3)
    data = np.frombuffer(fault_bytes, dtype=np.uint8)
    offset = 0
    n_vertices = int(np.frombuffer(data[offset : offset + 4], dtype=np.int32)[0])
    offset += 4
    vertices = np.frombuffer(
        data[offset : offset + 4 * 3 * n_vertices], dtype=np.float32
    ).reshape((n_vertices, 3))
    offset += 4 * 3 * n_vertices
    n_triangles = int(np.frombuffer(data[offset : offset + 4], dtype=np.int32)[0])
    offset += 4
    triangles = np.frombuffer(
        data[offset : offset + 4 * 3 * n_triangles], dtype=np.int32
    ).reshape((n_triangles, 3))
    offset += 4 * 3 * n_triangles
    if offset != len(data):
        raise ValueError("Malformed fault file, extra data at the end")
    LOGGER.info(f"Loaded fault with {n_vertices} vertices and {n_triangles} triangles")
    return KarstNSimFault(vertices=vertices, triangles=triangles)


def load_fault_from_off(bytes: bytes) -> KarstNSimFault:
    """Parse an OFF mesh into a KarstNSimFault.
    Replaces load_fault() which parsed the custom Angular binary format.
    OFF format: header, then 'n_verts n_faces n_edges', then xyz lines, then face lines."""
    lines = bytes.decode("utf-8").splitlines()
    # skip "OFF" header line
    start = 1 if lines[0].strip() == "OFF" else 0
    n_verts, n_faces, _ = map(int, lines[start].split())
    vertices = np.array(
        [list(map(float, lines[start + 1 + i].split())) for i in range(n_verts)],
        dtype=np.float32,
    )
    triangles = np.array(
        [
            list(map(int, lines[start + 1 + n_verts + i].split()))[1:]
            for i in range(n_faces)
        ],
        dtype=np.int32,
    )
    LOGGER.info(
        f"Loaded fault with {n_verts} vertices and {n_faces} triangles from OFF"
    )
    return KarstNSimFault(vertices=vertices, triangles=triangles)


def build_karstnsim_content(
    data: "KarstNSimData",
    dem_bytes: bytes,
    voxels_str: str,
    fault_bytes: dict[int, bytes],
) -> KarstNSimContent:
    # dem: same logic as read_zip
    surface_data = np.frombuffer(dem_bytes, dtype=np.float32)
    surface_data = surface_data.reshape(
        (data.dem_resolution.n_rows, data.dem_resolution.n_cols)
    )
    voxels_lines = voxels_str.splitlines()
    voxels_header, voxels = load_voxels(voxels_lines)
    compute_resolution = Vec3Int(
        x=voxels_header.nx, y=voxels_header.ny, z=voxels_header.nz
    )

    # resample + flip: same arithmetic as read_zip
    surface_data = surface_data[
        :: data.dem_resolution.n_rows // compute_resolution["y"],
        :: data.dem_resolution.n_cols // compute_resolution["x"],
    ]
    surface_data = np.flipud(surface_data).copy()

    if surface_data.shape[0] < 2 or surface_data.shape[1] < 2:
        raise ValueError("Surface data grid must have at least 2 rows and 2 columns")

    surface_resolution = Point2D(
        x=data.project_box.width / (surface_data.shape[1] - 1),
        y=data.project_box.height / (surface_data.shape[0] - 1),
    )
    resampled_dem_resolution = KarstNSimDemResolution(
        n_cols=surface_data.shape[1],
        n_rows=surface_data.shape[0],
    )
    faults = [load_fault_from_off(bytes) for bytes in fault_bytes.values()]

    return KarstNSimContent(
        simulation_params=data.simulation_params,
        project_box=data.project_box,
        dem_resolution=data.dem_resolution,
        surface_data=surface_data,
        stratigraphy=KarstNSimStratigraphy(data.stratigraphy),
        compute_resolution=compute_resolution,
        voxels_header=voxels_header,
        voxels=voxels,
        voxels_units=KarstNSimVoxelsUnits(data.voxels_units),
        faults=faults,
        springs=data.springs,
        gwbs=data.gwbs,
        surface_resolution=surface_resolution,
        resampled_dem_resolution=resampled_dem_resolution,
    )
