import logging
import time

import numpy as np
from pykarstnsim.config import KarstConfig
from pykarstnsim.karstnsim import run_simulation
from pykarstnsim.models.spring import Spring
from pykarstnsim.models.surface import Surface

from geocruncher.computations import KarstNSimData
from geocruncher.karst.converters import load_project_box, load_sinks, load_water_tables
from geocruncher.karst.input import build_karst_content
from geocruncher.karst.output import serialize_output

LOGGER = logging.getLogger(__name__)


def run_karst_simulation(
    data: KarstNSimData,
    dem_bytes: bytes,
    voxels_str: str,
    fault_off_bytes: dict[int, bytes],
) -> bytes:
    content = build_karst_content(data, dem_bytes, voxels_str, fault_off_bytes)

    project_box = load_project_box(
        content.project_box,
        content.stratigraphy,
        content.compute_resolution,
        content.voxels,
        content.voxels_units.root,
        content.simulation_params.r_min_pervious,
        content.simulation_params.r_min_impervious,
    )
    dem = Surface.from_dem_grid(
        content.surface_data,
        content.project_box.width,
        content.project_box.height,
    )
    springs = [
        Spring(origin=(s.x, s.y, s.z), index=i + 1, water_table_index=0, radius=0.0)
        for i, s in enumerate(content.springs)
    ]
    gwb_surfaces = load_water_tables(content.voxels, content.project_box)
    ordered_gwb_ids = sorted(gwb_surfaces.keys())
    water_tables = [gwb_surfaces[gwb_id] for gwb_id in ordered_gwb_ids]
    spring_to_wt_index = {
        gwb.spring_id: wt_index
        for wt_index, gwb_id in enumerate(ordered_gwb_ids, start=1)
        for gwb in content.gwbs
        if gwb.gwb_id == gwb_id
    }
    for spring, karst_spring in zip(springs, content.springs):
        if karst_spring.poi_id not in spring_to_wt_index:
            raise ValueError(
                f"Spring {spring.index} has no associated groundwater body"
            )
        spring.water_table_index = spring_to_wt_index[karst_spring.poi_id]

    faults = [
        Surface.from_vertices_and_triangles(f.vertices, f.triangles)
        for f in content.faults
    ]
    rng = np.random.default_rng(content.simulation_params.seed)
    sinks, connectivity_matrix = load_sinks(
        content.simulation_params.n_sinks,
        content.springs,
        content.resampled_dem_resolution,
        content.surface_resolution,
        content.surface_data,
        rng,
        len(springs),
    )
    max_dim = max(
        content.project_box.width / content.compute_resolution.x,
        content.project_box.height / content.compute_resolution.y,
        content.project_box.depth / content.compute_resolution.z,
    )
    config = KarstConfig()
    config.karstic_network_name = content.simulation_params.name
    config.selected_seed = content.simulation_params.seed
    config.k_pts = content.simulation_params.k_pts
    config.fraction_karst_perm = content.simulation_params.cohesion_factor
    config.nghb_radius = (
        max_dim * 3.0
        if content.simulation_params.search_radius == "auto"
        else content.simulation_params.search_radius
    )
    config.inception_surface_constraint_weight = (
        content.simulation_params.inception_surface_constraint_weight
    )
    config.max_inception_surface_distance = (
        max_dim * 3.0
        if content.simulation_params.max_inception_surface_distance == "auto"
        else content.simulation_params.max_inception_surface_distance
    )
    config.use_max_nghb_radius = True
    config.refine_surface_sampling = 1
    config.use_karstification_potential = True
    config.karstification_potential_weight = 1.0
    config.nb_deadend_points = 0
    config.create_vset_sampling = False

    start = time.time_ns()
    result = run_simulation(
        config,
        project_box=project_box,
        sinks=sinks,
        springs=springs,
        connectivity_matrix=connectivity_matrix,
        water_tables=water_tables,
        topo_surface=dem,
        inception_surfaces=faults,
    )
    if result is None:
        raise ValueError("Simulation returned no result")

    runtime_s = (time.time_ns() - start) / 1e9
    LOGGER.info(
        "Simulation completed in %.2f seconds, %d segments",
        runtime_s,
        len(result.segments),
    )
    return serialize_output(
        result, content.simulation_params, content.compute_resolution, runtime_s
    )
