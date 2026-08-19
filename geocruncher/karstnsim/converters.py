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
from shapely import Polygon, make_valid

from geocruncher.geometry import (
    Vec2Float,
    Vec2Int,
    Vec3Int,
    elevation_at_xy_batch,
    random_points_in_polygon,
)
from geocruncher.karstnsim.models import (
    PERMEABILITY_MAP,
    GeologicalUnitInput,
    Permeability,
    ProjectBoxInput,
    SpringInput,
    StratigraphyInput,
)

LOGGER = logging.getLogger(__name__)

SKY = GeologicalUnitInput(
    name="Sky", permeability=Permeability.NonKarstified, strati_unit_id=0
)
DUMMY = GeologicalUnitInput(
    name="Dummy", permeability=Permeability.Undefined, strati_unit_id=0
)


def load_project_box(
    box: ProjectBoxInput,
    stratigraphy: StratigraphyInput,
    compute_resolution: Vec3Int,
    voxels: np.ndarray,
    voxels_units: list[int],
    is_base: bool,
    r_min_pervious: Literal["auto"] | float = "auto",
    r_min_impervious: Literal["auto"] | float = "auto",
) -> ProjectBox:
    """Build a ProjectBox object made of the karstification potential and density for each compute-cell in the project box."""

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

    # Unit lookup
    units_by_id = {unit.strati_unit_id: unit for unit in units}
    # Build rank -> unit lookup
    rank_to_unit: dict[int, GeologicalUnitInput] = {}
    for j, unit_id in enumerate(voxels_units):
        # Get the unit with the matching strati_unit_id
        unit = units_by_id.get(unit_id)
        if unit:
            if is_base:
                rank_to_unit[rank_count - j] = unit
            else:
                rank_to_unit[j + 1] = unit
        else:
            LOGGER.warning(f"No geological unit found with strati_unit_id={unit_id}")

    # If the number of units is less than the number of ranks, there must be a dummy unit to fill the remaining ranks
    if len(voxels_units) < rank_count:
        if is_base:
            rank_to_unit[1] = DUMMY
        else:
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

    # Flatten with Fortran ("F") order, u changing fastest
    karstification_potential = potential_vol.flatten(order="F").tolist()
    densities = density_vol.flatten(order="F").tolist()

    project_box = ProjectBox(
        basis, u, v, w, cells_u, cells_v, cells_w, densities, karstification_potential
    )
    return project_box


def load_sinks(
    n_sinks: int,
    springs: list[SpringInput],
    dem_resolution: Vec2Int,
    surface_resolution: Vec2Float,
    surface_data: np.ndarray,
    rng: np.random.Generator,
    num_springs: int,
) -> tuple[list[Sink], ConnectivityMatrix]:
    """Generate random sink points within the catchment polygons of the springs and build a connectivity matrix between sinks and springs."""

    if n_sinks <= 0:
        return [], ConnectivityMatrix([])

    catchment_ids: list[str | int] = []
    catchment_polygons: list[Polygon] = []
    for spring in springs:
        coords = np.array(spring.catchment, dtype=np.float64)
        polygon = Polygon(coords)

        if not polygon.is_valid:
            polygon = make_valid(polygon)
        if (
            polygon.is_empty
            or not polygon.is_valid
            or polygon.geom_type not in {"Polygon", "MultiPolygon"}
        ):
            raise ValueError(
                f"Could not construct a valid polygon for catchment {spring.poi_id}"
            )

        catchment_ids.append(spring.poi_id)
        catchment_polygons.append(polygon)

    if not catchment_polygons:
        raise ValueError("No valid catchment polygons.")

    areas = np.array([poly.area for poly in catchment_polygons], dtype=np.float64)

    weights = (
        np.full(len(catchment_polygons), 1.0 / len(catchment_polygons))
        if np.all(areas == 0)
        else areas / areas.sum()
    )

    # Assign sinks randomly to each catchment polygon, weighted by area
    if len(catchment_polygons) == 1:
        assignments = np.zeros(n_sinks, dtype=int)
    else:
        assignments = rng.choice(len(catchment_polygons), size=n_sinks, p=weights)

    counts = np.bincount(assignments, minlength=len(catchment_polygons))

    sinks: list[Sink] = []
    connectivity = np.full(
        (n_sinks, num_springs),
        ConnectivityType.NOT_CONNECTED,
        dtype=object,
    )
    sink_offset = 0

    # Generate each catchment's assigned sinks and mark their spring connection
    # in one bulk assignment.
    for idx, polygon in enumerate(catchment_polygons):
        count = int(counts[idx])
        if count == 0:
            continue

        pts = random_points_in_polygon(polygon, count, rng)
        elevations = elevation_at_xy_batch(
            pts[:, 0], pts[:, 1], surface_data, surface_resolution, dem_resolution
        )

        next_offset = sink_offset + count
        connectivity[sink_offset:next_offset, idx] = ConnectivityType.CONNECTED

        sinks.extend(
            Sink(
                origin=(float(x), float(y), float(z)),
                index=sink_offset + local_index + 1,
                order=1,
                radius=0.0,
            )
            for local_index, ((x, y), z) in enumerate(zip(pts, elevations))
        )
        sink_offset = next_offset

    return sinks, ConnectivityMatrix(connectivity.tolist())


def load_water_tables(
    voxels: np.ndarray,
    project_box: ProjectBoxInput,
) -> dict[int, Surface]:
    """Build a water-table surface for each groundwater body present in the voxels."""

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

       v1 = vertex_indices[:-1, :-1]
       v2 = vertex_indices[:-1, 1:]
       v3 = vertex_indices[1:, :-1]
       v4 = vertex_indices[1:, 1:]

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
