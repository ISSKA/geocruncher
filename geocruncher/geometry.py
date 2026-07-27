from typing import TypedDict

import numpy as np
from shapely import Polygon, contains_xy


class Vec2Int(TypedDict):
    """2D Integer vector"""

    x: int
    y: int


class Vec2Float(TypedDict):
    """2D Float vector"""

    x: float
    y: float


class Vec3Int(Vec2Int):
    """3D Integer vector"""

    z: int


class Vec3Float(Vec2Float):
    """3D Float vector"""

    z: float


class Rectangle3D(TypedDict):
    """Rectangle defined by its bounds. Could be replaced with Box"""

    lowerLeft: Vec3Float
    upperRight: Vec3Float


class Line3D(TypedDict):
    """Line defined by its start and end"""

    start: Vec3Float
    end: Vec3Float


def random_points_in_polygon(
    poly: Polygon, n_points: int, rng: np.random.Generator
) -> np.ndarray:
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
        # Generate random x, y coordinates within the bounding box of the polygon
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


def elevation_at_xy_batch(
    xs: np.ndarray,
    ys: np.ndarray,
    surface_data: np.ndarray,
    surface_resolution: Vec2Float,
    dem_resolution: Vec2Int,
) -> np.ndarray:
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

    # Bilinear interpolation for each point (x, y) using the four surrounding DEM grid points
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
