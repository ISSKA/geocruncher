# Based on https://github.com/ISSKA/pykarstnsim-demo/tree/main/src/pykarstnsim_demo/converters


import logging
from typing import Literal

import numpy as np
from pykarstnsim.models import (
    ConnectivityMatrix,
    ConnectivityType,
    ProjectBox,
    Sink,
    Surface,
)
from shapely import Point, Polygon

from geocruncher.geometry import Vec2Float, Vec3Int
from geocruncher.karstnsim.models import (
    PERMEABILITY_MAP,
    KarstNSimDemResolution,
    KarstNSimGeologicalUnit,
    KarstNSimProjectBox,
    KarstNSimSpring,
    KarstNSimStratigraphy,
    Permeability,
)

LOGGER = logging.getLogger(__name__)

SKY = KarstNSimGeologicalUnit(
    name="Sky", permeability=Permeability.NonKarstified, strati_unit_id=0
)
DUMMY = KarstNSimGeologicalUnit(
    name="Dummy", permeability=Permeability.Undefined, strati_unit_id=0
)


def load_project_box(
    box: KarstNSimProjectBox,
    stratigraphy: KarstNSimStratigraphy,
    compute_resolution: Vec3Int,
    voxels: np.ndarray,
    voxels_units: list[int],
    r_min_pervious: Literal["auto"] | float = "auto",
    r_min_impervious: Literal["auto"] | float = "auto",
) -> ProjectBox:

    units = stratigraphy.root

    # move to local box coordinates
    basis = (0, 0, box.min_elevation)
    u = (box.width, 0.0, 0.0)
    v = (0.0, box.height, 0.0)
    w = (0.0, 0.0, box.depth)
    cells_u = compute_resolution["x"]
    cells_v = compute_resolution["y"]
    cells_w = compute_resolution["z"]

    # we will find the "top" altitude of each gwb cell
    gwbs = [0] * (cells_u * cells_v)

    NO_VALUE = -99999.0

    unique_ranks = voxels[:, :, :, 0].flatten()
    unique_ranks = np.unique(unique_ranks).tolist()
    LOGGER.debug(f"Unique ranks in voxel data: {unique_ranks}")

    rank_count = len(units)

    # TODO make it work for not base projects
    is_base = False

    rank_to_unit: dict[int, KarstNSimGeologicalUnit] = {}

    j = 0
    for unit_id in voxels_units:
        unit = next(filter(lambda uN: uN.strati_unit_id == unit_id, units), None)
        if unit:
            id = rank_count - j if is_base else j + 1
            rank_to_unit[id] = unit
        else:
            LOGGER.warning(f"No geological unit found with strati_unit_id={unit_id}")
        j += 1

    # if the counts do not mach, there must be a dummy, so add it
    if len(voxels_units) < rank_count:
        id = 1 if is_base else rank_count
        rank_to_unit[id] = DUMMY

    # add the Sky, always rank 0
    rank_to_unit[0] = SKY

    for rank in unique_ranks:
        unit = rank_to_unit[rank]
        LOGGER.info(f"Rank {rank}: {unit.name} (permeability={unit.permeability})")

    densities = [NO_VALUE] * (cells_u * cells_v * cells_w)
    karstification_potential = [NO_VALUE] * (cells_u * cells_v * cells_w)

    if r_min_pervious == "auto":
        base_density = cells_w / w[2]
    else:
        base_density = r_min_pervious
    if r_min_impervious == "auto":
        sparse_density = base_density * 2
    else:
        sparse_density = r_min_impervious

    if base_density > 1 or sparse_density > 1:
        raise ValueError(
            f"Density modifier too high, resulting density > 1 (base={base_density}, sparse={sparse_density})"
        )

    # for each cell of the compute resolution, get the corresponding rank from the voxels
    nx, ny, nz, _ = voxels.shape
    for iu in range(cells_u):
        for iv in range(cells_v):
            for iw in range(cells_w):
                index = iu + cells_u * (iv + cells_v * iw)
                # map (iu, iv, iw) in [0, cells_u/v/w] to (ix, iy, iz) in [0, nx/ny/nz]
                ix = min(int(iu / cells_u * nx), nx - 1)
                iy = min(int(iv / cells_v * ny), ny - 1)
                iz = min(int(iw / cells_w * nz), nz - 1)
                rank = voxels[ix, iy, iz, 0]
                gwb_id = voxels[ix, iy, iz, 1]
                if gwb_id > 0:
                    # in a gwb, set potential to 1.0 (will normalize later)
                    potential = 1.0
                    gwbs[iv * cells_w + iw] = max(gwbs[iv * cells_w + iw], gwb_id)
                elif rank > 0:
                    unit = rank_to_unit[rank]
                    potential = PERMEABILITY_MAP.get(unit.permeability, NO_VALUE)
                    if potential == NO_VALUE:
                        LOGGER.warning(
                            f"Unknown permeability '{unit.permeability}' for unit {unit.name}"
                        )
                else:
                    # ignore sky
                    continue

                karstification_potential[index] = potential
                if potential < 0:
                    # density is already NO_VALUE
                    continue
                densities[index] = base_density if potential > 0 else sparse_density

    project_box = ProjectBox(
        basis, u, v, w, cells_u, cells_v, cells_w, densities, karstification_potential
    )

    return project_box


def load_sinks(
    n_sinks: int,
    springs: list[KarstNSimSpring],
    dem_resolution: KarstNSimDemResolution,
    surface_resolution: Vec2Float,
    surface_data: np.ndarray,
    rng: np.random.Generator,
    num_springs: int,
) -> tuple[list[Sink], ConnectivityMatrix]:

    def random_points_in_polygon(poly: Polygon, n_points: int) -> np.ndarray:
        """Uniform random points inside a polygon via rejection sampling."""

        if n_points <= 0:
            return np.empty((0, 2), dtype=np.float64)

        minx, miny, maxx, maxy = poly.bounds

        accepted: list[tuple[float, float]] = []
        remaining = n_points
        # heuristic: batch size = 2x remaining (increase if polygon occupies small fraction)
        while remaining > 0:
            batch_size = max(remaining * 2, 32)
            xs = rng.uniform(minx, maxx, size=batch_size)
            ys = rng.uniform(miny, maxy, size=batch_size)
            for x, y in zip(xs, ys):
                if poly.covers(Point(x, y)):
                    accepted.append((x, y))
                    remaining -= 1
                    if remaining == 0:
                        break
        pts = np.asarray(accepted, dtype=np.float64)
        return pts

    def elevation_at_xy(x: float, y: float) -> float:
        """Bilinear interpolation of elevation at given (x,y) in local box coordinates"""
        # convert to grid indices
        col = x / surface_resolution["x"]
        row = y / surface_resolution["y"]
        if (
            col < 0
            or col >= dem_resolution.n_cols - 1
            or row < 0
            or row >= dem_resolution.n_rows - 1
        ):
            raise ValueError(f"Point ({x},{y}) out of DEM bounds")
        col0 = int(np.floor(col))
        row0 = int(np.floor(row))
        col1 = col0 + 1
        row1 = row0 + 1
        # fractional part
        dc = col - col0
        dr = row - row0
        # bilinear interpolation
        z00 = surface_data[row0, col0]
        z10 = surface_data[row0, col1]
        z01 = surface_data[row1, col0]
        z11 = surface_data[row1, col1]
        z0 = z00 * (1 - dc) + z10 * dc
        z1 = z01 * (1 - dc) + z11 * dc
        z = z0 * (1 - dr) + z1 * dr
        return float(z)

    if n_sinks <= 0:
        empty_matrix = ConnectivityMatrix([])
        return [], empty_matrix

    catchment_ids: list[str | int] = []
    catchment_polygons: list[Polygon] = []
    for spring in springs:
        coords = np.array(spring["catchment"], dtype=np.float64)
        polygon = Polygon(coords)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        catchment_ids.append(spring["poi_id"])
        catchment_polygons.append(polygon)

    areas = np.array([poly.area for poly in catchment_polygons], dtype=np.float64)
    if np.all(areas == 0):
        weights = np.full(len(catchment_polygons), 1.0 / len(catchment_polygons))
    else:
        weights = areas / areas.sum()

    if len(catchment_polygons) == 1:
        assignments = np.zeros(n_sinks, dtype=int)
    else:
        # get random assignments of sinks to catchments based on weights
        assignments = rng.choice(len(catchment_polygons), size=n_sinks, p=weights)
    counts = np.bincount(assignments, minlength=len(catchment_polygons))

    sinks: list[Sink] = []
    connectivity_matrix_data: list[list[ConnectivityType]] = []
    sink_index = 1
    for idx, (spring_id, polygon) in enumerate(zip(catchment_ids, catchment_polygons)):
        count = int(counts[idx])
        if count == 0:
            continue
        LOGGER.info(
            "Allocating %d sinks to spring %s catchment (area=%.2f)",
            count,
            spring_id,
            areas[idx],
        )
        sinks_pts = random_points_in_polygon(polygon, count)
        for x, y in sinks_pts:
            sinks.append(
                Sink(
                    origin=(float(x), float(y), elevation_at_xy(float(x), float(y))),
                    index=sink_index,
                    order=1,
                    radius=0.0,
                )
            )
            # Create connectivity row for this sink
            row = [ConnectivityType.NOT_CONNECTED] * num_springs
            row[idx] = ConnectivityType.CONNECTED  # idx is the spring index
            connectivity_matrix_data.append(row)
            sink_index += 1

    connectivity_matrix = ConnectivityMatrix(connectivity_matrix_data)
    return sinks, connectivity_matrix


def load_water_tables(
    voxels: np.ndarray,
    project_box: KarstNSimProjectBox,
) -> dict[int, Surface]:
    """Build a triangulated water-table surface for each groundwater body present in the voxels."""

    if voxels.ndim != 4 or voxels.shape[-1] < 2:
        raise ValueError(
            "Voxels array must have shape (nx, ny, nz, 2) including gwb identifiers"
        )

    nx, ny, nz, _ = voxels.shape
    if nz == 0:
        return {}

    dx = project_box.width / max(nx - 1, 1) if nx > 1 else 0.0
    dy = project_box.height / max(ny - 1, 1) if ny > 1 else 0.0
    dz = project_box.depth / nz

    gwb_ids = voxels[:, :, :, 1]
    unique_gwb_ids: list[int] = np.unique(gwb_ids).flatten().tolist()
    LOGGER.debug(f"Unique GWB IDs in voxel data: {unique_gwb_ids}")

    surfaces: dict[int, Surface] = {}

    for gwb_id in unique_gwb_ids:
        if gwb_id <= 0:
            continue

        # highest occupied z-layer for each (x, y) column within this groundwater body
        top_layer = np.full((nx, ny), -1, dtype=np.int32)
        gwb_mask = gwb_ids == gwb_id

        for ix in range(nx):
            column = gwb_mask[ix]
            for iy in range(ny):
                hits = np.flatnonzero(column[iy])
                if hits.size > 0:
                    top_layer[ix, iy] = int(hits[-1])

        valid_mask = top_layer >= 0
        if not valid_mask.any():
            continue

        xs, ys = np.where(valid_mask)
        x_min, x_max = int(xs.min()), int(xs.max())
        y_min, y_max = int(ys.min()), int(ys.max())

        width = x_max - x_min + 1
        height = y_max - y_min + 1

        vertex_indices = -np.ones((height, width), dtype=np.int32)
        vertices: list[list[float]] = []

        for local_y, global_y in enumerate(range(y_min, y_max + 1)):
            y_coord = global_y * dy
            for local_x, global_x in enumerate(range(x_min, x_max + 1)):
                top_idx = top_layer[global_x, global_y]
                if top_idx < 0:
                    continue
                x_coord = global_x * dx
                z_coord = (top_idx + 1) * dz + project_box.min_elevation
                vertex_indices[local_y, local_x] = len(vertices)
                vertices.append([x_coord, y_coord, z_coord])

        triangles: list[list[int]] = []
        for local_y in range(height - 1):
            for local_x in range(width - 1):
                v1 = vertex_indices[local_y, local_x]
                v2 = vertex_indices[local_y, local_x + 1]
                v3 = vertex_indices[local_y + 1, local_x]
                v4 = vertex_indices[local_y + 1, local_x + 1]
                if min(v1, v2, v3, v4) < 0:
                    continue
                triangles.append([v1, v2, v3])
                triangles.append([v2, v4, v3])

        if not triangles:
            LOGGER.warning(
                "Skipping groundwater body %s because no triangles could be generated.",
                gwb_id,
            )
            continue

        surfaces[gwb_id] = Surface.from_vertices_and_triangles(
            np.asarray(vertices, dtype=np.float64),
            np.asarray(triangles, dtype=np.int32),
        )
        LOGGER.info(
            "Built water table surface for GWB %s with %d vertices and %d triangles.",
            gwb_id,
            len(vertices),
            len(triangles),
        )

    return surfaces
