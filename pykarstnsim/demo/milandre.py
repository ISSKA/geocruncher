import logging

import numpy as np
import PyGeoAlgo as ga
import pyproj
from shapely.geometry import Point, Polygon

from pykarstnsim.karstnsim import run_simulation
from pykarstnsim.models import (
    ConnectivityMatrix,
    ProjectBox,
    Sink,
    Spring,
    Surface,
    surface,
)
from pykarstnsim.models.connectivity_matrix import ConnectivityType

logging.basicConfig(level=logging.INFO)

from pathlib import Path

from pykarstnsim.config import KarstConfig

LOGGER = logging.getLogger(__name__)

input_root = Path(__file__).parent / "milandre"

# Instantiate config
CONFIG = KarstConfig()

CONFIG.karstic_network_name = "milandre"

# set seed for reproducibility
CONFIG.selected_seed = 42
rng = np.random.default_rng(CONFIG.selected_seed)

# disable deadend points for demo
CONFIG.nb_deadend_points = 0
CONFIG.k_pts = 10

CONFIG.use_karstification_potential = True
CONFIG.karstification_potential_weight = 1.0
CONFIG.fraction_karst_perm = 0.9  # cohesion factor

# number of cells in each direction (u,v,w)
compute_resolution = (100, 100, 29)

project_coordinate_system = 21781  # CH1903+ / LV95
box = {
    "x": 563987.6,
    "y": 252987.6,
    "width": 7524.7,
    "height": 7524.7,
    "min_elevation": 0,
    "max_elevation": 1100,
}
dem_resolution = 25.0  # meters
dem_n_cols = int(box["width"] / dem_resolution) + 1
dem_n_rows = int(box["height"] / dem_resolution) + 1
n_sinks = 1000
CONFIG.refine_surface_sampling = 1  # 1 refinement step
CONFIG.use_max_nghb_radius = True
CONFIG.nghb_radius = box["width"] / compute_resolution[0] * 3.0

CONFIG.inception_surface_constraint_weight = 1.0
CONFIG.max_inception_surface_distance = box["width"] / compute_resolution[0] * 2.0

permeabilities_map = {"Karstified": 0.8, "NonKarstified": 0.0, "Undefined": 0.0}

units = [
    {
        "unit": {
            "colour": "#63d296",
            "id": 842,
            "name": "Fm Reuchenette",
            "permeability": "Karstified",
            "stratiUnitId": 187,
        }
    },
    {
        "unit": {
            "colour": "#4ae0e3",
            "id": 840,
            "name": "Fm Courgenay",
            "permeability": "Karstified",
            "stratiUnitId": 188,
        }
    },
    {
        "unit": {
            "colour": "#00858a",
            "id": 837,
            "name": "Marnes_Ast_Nat (Mb Bure-Vellerat)",
            "permeability": "NonKarstified",
            "stratiUnitId": 189,
        }
    },
    {
        "unit": {
            "colour": "#008a00",
            "id": 841,
            "name": "Calcaires_Astartes_Nat (Mb Vorburg)",
            "permeability": "Karstified",
            "stratiUnitId": 190,
        }
    },
    {
        "unit": {
            "colour": "#bfbfbf",
            "id": 839,
            "name": "Rauracien (St_Ursanne)",
            "permeability": "Karstified",
            "stratiUnitId": 191,
        }
    },
    {
        "unit": {
            "colour": "#8a3a3a",
            "id": 843,
            "name": "Oxf_inf",
            "permeability": "NonKarstified",
            "stratiUnitId": 192,
        }
    },
]

catchment_wgs84 = {
    "type": "Polygon",
    "coordinates": [
        [
            [7.013126423217356, 47.48728100779349],
            [7.018191990484005, 47.48356884981895],
            [7.011323424698711, 47.474751423229165],
            [7.022999986533699, 47.46169659502515],
            [7.009949711541683, 47.455951443369955],
            [7.008404284239994, 47.44811613395019],
            [7.000591290659251, 47.44614261273751],
            [6.999818577008386, 47.44254364813588],
            [6.976293739193827, 47.441324588172975],
            [6.970112029987067, 47.4318614002635],
            [6.965132319792749, 47.42982920544397],
            [6.965561605154327, 47.447477649895966],
            [6.9782684518570965, 47.46541029836714],
            [6.984536018136148, 47.47678188285846],
            [6.99380858194629, 47.4851929512123],
            [7.005227572564282, 47.4912828842337],
            [7.010207282758598, 47.49337069872157],
            [7.01544456416987, 47.49337069872157],
            [7.01638899196536, 47.49064492436224],
            [7.015787992459158, 47.489368981370724],
            [7.012353709566531, 47.48878899703638],
            [7.013126423217356, 47.48728100779349],
        ]
    ],
}

with open(input_root / "milandre_surface.f32.array", "rb") as f:
    surface_data_raw = f.read()
    print(f"Loaded surface data of length {len(surface_data_raw)} bytes")

# surface is a raw float32 array
surface_data = np.frombuffer(surface_data_raw, dtype=np.float32)
# reshape to 2D array
surface_data = surface_data.reshape((dem_n_rows, dem_n_cols))
print(f"Reshaped surface data to {surface_data.shape}")
# resample to target compute resolution using a bilinear filter
surface_data = surface_data[
    :: dem_n_rows // compute_resolution[1], :: dem_n_cols // compute_resolution[0]
]
# flip y axis to have row 0 = min y
surface_data = np.flipud(surface_data)
print(f"Resampled surface data to {surface_data.shape}")
dem_n_rows, dem_n_cols = surface_data.shape
dem_x_resolution = box["width"] / (dem_n_cols - 1)
dem_y_resolution = box["height"] / (dem_n_rows - 1)


def load_voxels() -> np.ndarray:
    """Load voxel grid and return as ndarray of shape (nx, ny, nz, 2) where last dimension is (rank, gwb_id)"""
    # file has 3 lines:
    # format is:
    # XMIN=563987.601 XMAX=571512.301 YMIN=252987.602 YMAX=260512.302 ZMIN=0.0 ZMAX=1100.0 NUMBERX=200 NUMBERY=200 NUMBERZ=29 NOVALUE=0
    # rank gwb_id
    # ... ...
    voxels_lines = (input_root / "milandre_voxels.txt").read_text().splitlines()
    if len(voxels_lines) < 3:
        raise ValueError("Voxel file must have at least 3 lines")

    # parse the header
    header = voxels_lines[0]
    header_parts = header.split()
    if len(header_parts) != 10:
        raise ValueError("Malformed voxel header line (expected 12 tokens)")
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
    print(f"Loaded voxel grid with shape {voxels.shape}")

    return voxels


def load_project_box(voxels: np.ndarray) -> ProjectBox:

    # move to local box coordinates
    basis = (0, 0, box["min_elevation"])
    u = (box["width"], 0.0, 0.0)
    v = (0.0, box["height"], 0.0)
    w = (0.0, 0.0, box["max_elevation"] - box["min_elevation"])
    cells_u = compute_resolution[0]
    cells_v = compute_resolution[1]
    cells_w = compute_resolution[2]

    # we will find the "top" altitude of each gwb cell
    gwbs = [0] * (cells_u * cells_v)

    NO_VALUE = -99999.0

    unique_ranks = voxels[:, :, :, 0].flatten()
    unique_ranks = np.unique(unique_ranks)
    print(f"Unique ranks in voxel data: {unique_ranks}")

    # TODO: only works for project in "base" mode
    def rank_to_unit(rank: int) -> dict:
        if rank == 0:
            return {
                "colour": "#87ceeb",
                "id": 0,
                "name": "Sky",
                "permeability": "Undefined",
                "stratiUnitId": 0,
            }
        elif 1 <= rank <= len(units):
            return units[len(units) - rank]["unit"]
        else:
            return {
                "colour": "#000000",
                "id": 838,
                "name": "Dummy",
                "permeability": "Undefined",
                "stratiUnitId": 0,
            }

    for rank in unique_ranks:
        unit = rank_to_unit(rank)
        print(f"Rank {rank}: {unit['name']}")

    densities = [NO_VALUE] * (cells_u * cells_v * cells_w)
    karstification_potential = [NO_VALUE] * (cells_u * cells_v * cells_w)
    # for each cell of the compute resolution, get the corresponding rank from the voxels
    nx, ny, nz, _ = voxels.shape
    for iu in range(cells_u):
        for iv in range(cells_v):
            for iw in range(cells_w):
                index = iu * (cells_v * cells_w) + iv * cells_w + iw
                # map (iu, iv, iw) in [0, cells_u/v/w] to (ix, iy, iz) in [0, nx/ny/nz]
                ix = min(int(iu / cells_u * nx), nx - 1)
                iy = min(int(iv / cells_v * ny), ny - 1)
                iz = min(int(iw / cells_w * nz), nz - 1)
                rank = voxels[ix, iy, iz, 0]
                gwb_id = voxels[ix, iy, iz, 1]
                if gwb_id > 0:
                    # in a gwb, set potential to 1.0 (will normalize later)
                    karstification_potential[index] = 1.0
                    gwbs[iv * cells_w + iw] = max(gwbs[iv * cells_w + iw], gwb_id)
                elif rank > 0:
                    unit = rank_to_unit(rank)
                    potential = permeabilities_map.get(unit["permeability"], NO_VALUE)
                    karstification_potential[index] = potential
                    if potential == NO_VALUE:
                        print(
                            f"Warning: Unknown permeability '{unit['permeability']}' for unit id {unit['id']}"
                        )

    # pass two: look each column, count and normalize density by all non-no-value cells
    for iu in range(cells_u):
        for iv in range(cells_v):
            # count valid cells in this column
            valid_count = 0
            for iw in range(cells_w):
                index = iu * (cells_v * cells_w) + iv * cells_w + iw
                if karstification_potential[index] != NO_VALUE:
                    valid_count += 1
            if valid_count == 0:
                continue
            density_per_cell = 1.0 / valid_count
            for iw in range(cells_w):
                index = iu * (cells_v * cells_w) + iv * cells_w + iw
                if karstification_potential[index] != NO_VALUE:
                    densities[index] = density_per_cell

    project_box = ProjectBox(
        basis, u, v, w, cells_u, cells_v, cells_w, densities, karstification_potential
    )

    # debug: write to file
    Path(input_root / "debug_milandre_project_box.txt").write_text(
        project_box.to_string()
    )
    return project_box


def load_dem(surface_data: np.ndarray) -> Surface:
    surface_obj = surface.Surface.from_dem_grid(
        surface_data, width=box["width"], height=box["height"]
    )
    print(
        f"Created surface object with {surface_obj.surface.get_nb_pts()} vertices and {surface_obj.surface.get_nb_trgls()} triangles"
    )
    # debug: write to file
    Path(input_root / "debug_milandre_surface.txt").write_text(surface_obj.to_string())
    return surface_obj


def load_springs() -> list[Spring]:
    springs = [
        Spring(
            origin=(567965 - box["x"], 259700 - box["y"], 373),
            index=1,  # 1-based index
            water_table_index=0,
            radius=0.0,
        )
    ]
    # debug: write to file
    Path(input_root / "debug_milandre_springs.txt").write_text(
        Spring.to_string(springs)
    )
    return springs


def load_water_tables(springs: list[Spring]) -> list[Surface]:
    water_tables: list[Surface] = []

    for i, spring in enumerate(springs):
        # horizontal plane at spring elevation - 5m
        z = spring.origin.z - 5.0

        # clip to last 10% of the height of the box
        ny = compute_resolution[1]
        nx = compute_resolution[0]
        clip_start = int(ny * 0.8)
        ys = np.linspace(0.0, box["height"], ny)[clip_start:]
        xs = np.linspace(0.0, box["width"], nx)

        # create vertices only for clipped region
        vertices = np.array([[x, y, z] for y in ys for x in xs])

        # build triangles for regular grid in clipped region
        clipped_ny = len(ys)
        triangles = []
        for row in range(clipped_ny - 1):
            for col in range(nx - 1):
                idx = row * nx + col
                triangles.append([idx, idx + 1, idx + nx])
                triangles.append([idx + 1, idx + nx + 1, idx + nx])
        triangles = np.array(triangles)

        water_table_surface = Surface.from_vertices_and_triangles(vertices, triangles)
        spring.water_table_index = i + 1  # 1-based index

        # debug: write to file
        Path(
            input_root / f"debug_milandre_water_table_spring_{spring.index}.txt"
        ).write_text(water_table_surface.to_string())

        water_tables.append(water_table_surface)

    return water_tables


def load_faults() -> list[Surface]:
    faults: list[Surface] = []

    fault_files = sorted(input_root.glob("milandre_faults_*.draco"))
    for fault_file in fault_files:
        fault_raw = fault_file.read_bytes()
        vertices, triangles = ga.FileIO.load_from_bytes(fault_raw).to_numpy()

        # need to offset vertices to local box coordinates
        vertices[:, 0] -= box["x"]
        vertices[:, 1] -= box["y"]
        # elevation is absolute, no change needed

        inception_surface = Surface.from_vertices_and_triangles(vertices, triangles)

        # debug: write to file
        Path(input_root / f"debug_{fault_file.stem}.txt").write_text(
            inception_surface.to_string()
        )

        faults.append(inception_surface)

    return faults


def load_sinks(catchment_wgs84, surface_data: np.ndarray) -> list[Sink]:
    transformer = pyproj.Transformer.from_crs(
        "EPSG:4326", f"EPSG:{project_coordinate_system}", always_xy=True
    )
    catchment_proj_coord = {
        "type": "Polygon",
        "coordinates": [
            [
                list(transformer.transform(lon, lat))
                for lon, lat in catchment_wgs84["coordinates"][0]
            ]
        ],
    }
    catchment = np.array(catchment_proj_coord["coordinates"][0])
    catchment[:, 0] -= box["x"]
    catchment[:, 1] -= box["y"]

    def random_points_in_polygon(poly_coords: np.ndarray, n_points: int):
        """Uniform random points inside a (nearly convex) polygon via rejection.

        Strategy:
        1. Build shapely Polygon
        2. Sample candidate points uniformly in polygon's bounding box in batches
        3. Keep those contained in polygon until we have n_points

        This avoids relying on unconstrained Delaunay triangulation which leaked
        points outside the concave polygon.
        """

        poly = Polygon(poly_coords)
        minx, miny, maxx, maxy = poly.bounds

        accepted: list[tuple[float, float]] = []
        remaining = n_points
        # heuristic: batch size = 2x remaining (increase if polygon occupies small fraction)
        while remaining > 0:
            batch_size = max(remaining * 2, 32)
            xs = rng.uniform(minx, maxx, size=batch_size)
            ys = rng.uniform(miny, maxy, size=batch_size)
            for x, y in zip(xs, ys):
                if poly.contains(Point(x, y)):
                    accepted.append((x, y))
                    remaining -= 1
                    if remaining == 0:
                        break
        pts = np.asarray(accepted)
        # quick sanity: all points should be inside
        # (avoid expensive per-point re-check unless debugging)
        return pts

    def elevation_at_xy(x: float, y: float) -> float:
        """Bilinear interpolation of elevation at given (x,y) in local box coordinates"""
        # convert to grid indices
        col = x / dem_x_resolution
        row = y / dem_y_resolution
        if col < 0 or col >= dem_n_cols - 1 or row < 0 or row >= dem_n_rows - 1:
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

    sinks_pts = random_points_in_polygon(catchment, n_sinks)

    sinks = [
        Sink(origin=(x, y, elevation_at_xy(x, y)), index=i + 1, order=1, radius=0.0)
        for i, (x, y) in enumerate(sinks_pts)
    ]

    # debug: write to file
    Path(input_root / "debug_milandre_sinks.txt").write_text(Sink.to_string(sinks))

    return sinks


def create_connectivity_matrix(
    sinks: list[Sink], springs: list[Spring]
) -> ConnectivityMatrix:
    # row = sink_i ,col = spring_j
    # for now, all connection are set to uncertain
    matrix: list[list[ConnectivityType]] = []
    for _ in sinks:
        row = [ConnectivityType.UNCERTAIN] * len(springs)
        matrix.append(row)

    conn_matrix = ConnectivityMatrix(matrix)
    # debug: write to file
    Path(input_root / "debug_milandre_connectivity_matrix.txt").write_text(
        conn_matrix.to_string()
    )

    return conn_matrix


voxels = load_voxels()
surface_obj = load_dem(surface_data)
project_box = load_project_box(voxels)
springs = load_springs()
water_tables = load_water_tables(springs)
faults = load_faults()
sinks = load_sinks(catchment_wgs84, surface_data)
connectivity_matrix = create_connectivity_matrix(sinks, springs)

res = run_simulation(
    CONFIG,
    project_box=project_box,
    sinks=sinks,
    springs=springs,
    connectivity_matrix=connectivity_matrix,
    water_tables=water_tables,
    topo_surface=surface_obj,
    inception_surfaces=faults,
)

if res is None:
    LOGGER.error("Simulation failed, no result returned.")
    exit(1)

print("Simulation result:", res)

Path("milandre_output.txt").write_text(res.to_string())
