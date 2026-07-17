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
from shapely import Polygon, contains_xy

from geocruncher.geometry import Vec2Float, Vec2Int, Vec3Int
from geocruncher.karstnsim.models import (
    PERMEABILITY_MAP,
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

    NO_VALUE = -99999.0
    rank_count = len(units)

    # Build rank -> unit lookup
    rank_to_unit: dict[int, KarstNSimGeologicalUnit] = {}
    for j, unit_id in enumerate(voxels_units):
        # Find the unit with the matching strati_unit_id
        unit = next(filter(lambda uN: uN.strati_unit_id == unit_id, units), None)
        if unit:
            id = j + 1
            rank_to_unit[id] = unit
        else:
            LOGGER.warning(f"No geological unit found with strati_unit_id={unit_id}")

    if len(voxels_units) < rank_count:
        rank_to_unit[rank_count] = DUMMY
    rank_to_unit[0] = SKY

    # Build rank -> permeability lookup
    max_rank = int(voxels[:, :, :, 0].max()) + 1
    perm_lookup = np.full(max_rank, NO_VALUE, dtype=np.float64)
    for rank, unit in rank_to_unit.items():
        if rank < max_rank:
            perm_lookup[rank] = PERMEABILITY_MAP.get(unit.permeability, NO_VALUE)

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

    nx, ny, nz, _ = voxels.shape
    # Create index arrays the size of the compute resolution
    iu_idx = np.arange(cells_u)
    iv_idx = np.arange(cells_v)
    iw_idx = np.arange(cells_w)

    # Map each compute-cell index(iu, iv, iw) to a voxel index (ix, iy, iz)
    ix_arr = np.clip((iu_idx / cells_u * nx).astype(np.int32), 0, nx - 1)
    iy_arr = np.clip((iv_idx / cells_v * ny).astype(np.int32), 0, ny - 1)
    iz_arr = np.clip((iw_idx / cells_w * nz).astype(np.int32), 0, nz - 1)

    # Combine the index arrays to get the rank and gwb_id for each compute-cell
    # shape = (cells_u, cells_v, cells_w)
    rank_vol = voxels[
        ix_arr[:, None, None], iy_arr[None, :, None], iz_arr[None, None, :], 0
    ]
    gwb_vol = voxels[
        ix_arr[:, None, None], iy_arr[None, :, None], iz_arr[None, None, :], 1
    ]

    # Get the permeability for each rank
    potential_vol = np.where(rank_vol > 0, perm_lookup[rank_vol], NO_VALUE)

    # Where gwb_id > 0 (in a gwb), set potential to 1.0
    in_gwb = gwb_vol > 0
    potential_vol = np.where(in_gwb, 1.0, potential_vol)

    density_vol = np.full_like(potential_vol, NO_VALUE)
    density_vol[potential_vol > 0] = base_density
    density_vol[potential_vol == 0] = sparse_density

    # Flatten with Fortran order, u changing fastest
    karstification_potential = potential_vol.flatten(order="F").tolist()
    densities = density_vol.flatten(order="F").tolist()

    project_box = ProjectBox(
        basis, u, v, w, cells_u, cells_v, cells_w, densities, karstification_potential
    )
    return project_box


def load_sinks(
    n_sinks: int,
    springs: list[KarstNSimSpring],
    dem_resolution: Vec2Int,
    surface_resolution: Vec2Float,
    surface_data: np.ndarray,
    rng: np.random.Generator,
    num_springs: int,
) -> tuple[list[Sink], ConnectivityMatrix]:

    def random_points_in_polygon(poly: Polygon, n_points: int) -> np.ndarray:
        """Uniform random points inside a polygon via rejection sampling (polygon can be concave)."""
        if n_points <= 0:
            return np.empty((0, 2), dtype=np.float64)

        minx, miny, maxx, maxy = poly.bounds
        accepted: list[np.ndarray] = []
        remaining = n_points

        MAX_FAILED_ATTEMPTS = 20
        failed_attempts = 0

        while remaining > 0:
            # Oversample by 2× to reduce iterations
            batch_size = max(remaining * 2, 32)
            xs = rng.uniform(minx, maxx, size=batch_size)
            ys = rng.uniform(miny, maxy, size=batch_size)

            # Save only points that are inside the polygon
            inside = contains_xy(poly, xs, ys)
            pts = np.column_stack([xs[inside], ys[inside]])

            if len(pts) == 0:
                failed_attempts += 1
                if failed_attempts >= MAX_FAILED_ATTEMPTS:
                    raise RuntimeError(
                        f"random_points_in_polygon failed to sample {remaining} remaining points "
                        f"after {MAX_FAILED_ATTEMPTS} consecutive empty batches — "
                        f"polygon may be degenerate (area={poly.area})"
                    )
                continue

            failed_attempts = 0

            # Only take as many points as needed to reach n_points
            take = min(remaining, len(pts))
            accepted.append(pts[:take])
            remaining -= take

        return np.vstack(accepted) if accepted else np.empty((0, 2), dtype=np.float64)

    def elevation_at_xy_batch(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        """
        Vectorised bilinear interpolation of elevation for arrays of (x, y) points.
        """
        # Convert (x, y) to DEM grid coordinates
        cols = xs / surface_resolution["x"]
        rows = ys / surface_resolution["y"]

        out_of_bounds = (
            (cols < 0)
            | (cols >= dem_resolution["x"] - 1)
            | (rows < 0)
            | (rows >= dem_resolution["y"] - 1)
        )
        if out_of_bounds.any():
            bad = np.argmax(out_of_bounds)
            raise ValueError(f"Point ({xs[bad]},{ys[bad]}) out of DEM bounds")

        # Bilinear interpolation
        col0 = np.floor(cols).astype(np.int32)
        row0 = np.floor(rows).astype(np.int32)
        col1 = col0 + 1
        row1 = row0 + 1

        dc = cols - col0
        dr = rows - row0

        z00 = surface_data[row0, col0]
        z10 = surface_data[row0, col1]
        z01 = surface_data[row1, col0]
        z11 = surface_data[row1, col1]

        z0 = z00 * (1 - dc) + z10 * dc
        z1 = z01 * (1 - dc) + z11 * dc
        return z0 * (1 - dr) + z1 * dr

    if n_sinks <= 0:
        return [], ConnectivityMatrix([])

    catchment_ids: list[str | int] = []
    catchment_polygons: list[Polygon] = []
    for spring in springs:
        coords = np.array(spring["catchment"], dtype=np.float64)
        polygon = Polygon(coords)
        # Shapely trick to fix invalid polygons (self-intersections, duplicate points, ...)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        catchment_ids.append(spring["poi_id"])
        catchment_polygons.append(polygon)

    areas = np.array([poly.area for poly in catchment_polygons], dtype=np.float64)

    # Assign a number of sinks to each catchment polygon, weighted by area
    weights = (
        np.full(len(catchment_polygons), 1.0 / len(catchment_polygons))
        if np.all(areas == 0)
        else areas / areas.sum()
    )

    if len(catchment_polygons) == 1:
        assignments = np.zeros(n_sinks, dtype=int)
    else:
        assignments = rng.choice(len(catchment_polygons), size=n_sinks, p=weights)

    counts = np.bincount(assignments, minlength=len(catchment_polygons))

    sinks: list[Sink] = []
    connectivity_matrix_data: list[list[ConnectivityType]] = []
    sink_index = 1

    # Pre-build connectivity row with all springs marked as NOT_CONNECTED
    not_connected_row = np.full(num_springs, ConnectivityType.NOT_CONNECTED)

    # For each catchment polygon, generate the assigned number of random sink points and build the connectivity matrix
    for idx, polygon in enumerate(catchment_polygons):
        count = int(counts[idx])
        if count == 0:
            continue

        pts = random_points_in_polygon(polygon, count)
        elevations = elevation_at_xy_batch(pts[:, 0], pts[:, 1])

        # Build sinks and connectivity matrix rows for each generated sink point
        for (x, y), z in zip(pts, elevations):
            sinks.append(
                Sink(
                    origin=(float(x), float(y), float(z)),
                    index=sink_index,
                    order=1,
                    radius=0.0,
                )
            )
            row = not_connected_row.copy()
            row[idx] = ConnectivityType.CONNECTED
            connectivity_matrix_data.append(row.tolist())
            sink_index += 1

    return sinks, ConnectivityMatrix(connectivity_matrix_data)


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

    # Compute the size of each voxel in the project box
    dx = project_box.width / max(nx - 1, 1) if nx > 1 else 0.0
    dy = project_box.height / max(ny - 1, 1) if ny > 1 else 0.0
    dz = project_box.depth / nz

    gwb_ids = voxels[:, :, :, 1]
    unique_gwb_ids: list[int] = np.unique(gwb_ids).flatten().tolist()

    surfaces: dict[int, Surface] = {}

    for gwb_id in unique_gwb_ids:
        # No gwb
        if gwb_id <= 0:
            continue
        # (nx, ny, nz) True where the voxel belongs to this gwb
        gwb_mask = gwb_ids == gwb_id

        # Reverse z, so argmax first hit (True) is the top layer
        top_layer = (nz - 1) - np.argmax(gwb_mask[:, :, ::-1], axis=2)
        # For each (x, y) column, check if there is any voxel belonging to this gwb
        has_any = gwb_mask.any(axis=2)
        # Set top_layer to -1 where there is no voxel belonging to this gwb
        top_layer = np.where(has_any, top_layer, -1).astype(np.int32)

        valid_mask = top_layer >= 0
        if not valid_mask.any():
            continue

        # Find the bounding box of valid cells in the top_layer
        xs_idx, ys_idx = np.where(valid_mask)
        x_min, x_max = int(xs_idx.min()), int(xs_idx.max())
        y_min, y_max = int(ys_idx.min()), int(ys_idx.max())

        width = x_max - x_min + 1
        height = y_max - y_min + 1

        # Crop the top_layer to the bounding box
        top_crop = top_layer[x_min : x_max + 1, y_min : y_max + 1]
        valid_crop = top_crop >= 0

        # Assign vertex indices: -1 for invalid cells, sequential for valid ones
        vertex_indices = np.full((height, width), -1, dtype=np.int32)
        # valid_crop is (width, height), we have to transpose to (height, width) for row-major layout
        valid_crop_T = valid_crop.T
        n_valid = int(valid_crop_T.sum())
        # Assign sequential indices to valid vertices
        vertex_indices[valid_crop_T] = np.arange(n_valid, dtype=np.int32)

        # Compute the global coordinates of valid vertices
        row_idx, col_idx = np.where(valid_crop_T)
        global_x_coords = (col_idx + x_min) * dx
        global_y_coords = (row_idx + y_min) * dy
        # Transpose top_crop to match the row-major layout of valid_crop_T
        z_coords = (top_crop.T[valid_crop_T] + 1) * dz + project_box.min_elevation

        vertices = np.column_stack([global_x_coords, global_y_coords, z_coords])

        local_y = np.arange(height - 1)
        local_x = np.arange(width - 1)
        # Get all combinations of local (y, x) coordinates (top-left corners of quads)
        ly, lx = np.meshgrid(local_y, local_x, indexing="ij")
        ly = ly.ravel()
        lx = lx.ravel()

        # Get the vertex indices for the four corners of each quad
        v1 = vertex_indices[ly, lx]
        v2 = vertex_indices[ly, lx + 1]
        v3 = vertex_indices[ly + 1, lx]
        v4 = vertex_indices[ly + 1, lx + 1]

        # Discard quads where corners are invalid (vertex index -1)
        valid_quads = (v1 >= 0) & (v2 >= 0) & (v3 >= 0) & (v4 >= 0)
        v1, v2, v3, v4 = (
            v1[valid_quads],
            v2[valid_quads],
            v3[valid_quads],
            v4[valid_quads],
        )

        if len(v1) == 0:
            LOGGER.warning(
                "Skipping groundwater body %s because no triangles could be generated.",
                gwb_id,
            )
            continue

        # Each quad -> 2 triangles: (v1,v2,v3) and (v2,v4,v3)
        tri_a = np.column_stack([v1, v2, v3])
        tri_b = np.column_stack([v2, v4, v3])
        # Reshape from (n_quads, 2, 3) to (n_triangles, 3)
        triangles = np.stack([tri_a, tri_b], axis=1).reshape(-1, 3)

        surfaces[gwb_id] = Surface.from_vertices_and_triangles(
            vertices.astype(np.float64),
            triangles.astype(np.int32),
        )

    return surfaces
