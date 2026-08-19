# Based on https://github.com/ISSKA/pykarstnsim-demo/blob/main/demo.py


import json

import numpy as np
from pykarstnsim.config import KarstConfig
from pykarstnsim.karstnsim import run_simulation
from pykarstnsim.models.spring import Spring
from pykarstnsim.models.surface import Surface

from geocruncher.generated_network.converters import (
    load_project_box,
    load_sinks,
    load_water_tables,
)
from geocruncher.generated_network.input import build_karstnsim_content
from geocruncher.generated_network.models import GeneratedNetworkData
from geocruncher.generated_network.serializers import serialize_karstnsim_result
from geocruncher.profiler import (
    PROFILES,
    ProfilerMetadata,
    profile_step,
    set_profiler,
    start_step,
)


def run_karstnsim(
    data: GeneratedNetworkData,
    dem_bytes: bytes,
    voxels_str: str,
    fault_bytes: dict[int, bytes],
    metadata: ProfilerMetadata | None = None,
) -> bytes:
    """Run the karstnsim simulation and return the result as bytes."""
    profiler = set_profiler(PROFILES["karstnsim"])

    content = build_karstnsim_content(data, dem_bytes, voxels_str, fault_bytes)

    profiler.set_metadata(
        "voxel_count",
        content.compute_resolution["x"]
        * content.compute_resolution["y"]
        * content.compute_resolution["z"],
    )
    profiler.set_metadata("num_springs", len(content.springs))
    profiler.set_metadata("num_gwbs", len(content.gwbs))
    profiler.set_metadata(
        "fault_triangle_count",
        sum(len(f.triangles) for f in content.faults),
    )
    profiler.set_metadata("num_sinks", content.simulation_params.n_sinks)
    profiler.set_metadata("sampling_radius", content.simulation_params.r_min_pervious)
    profiler.set_metadata("k_pts", content.simulation_params.k_pts)
    profiler.set_metadata("search_radius", content.simulation_params.search_radius)
    profiler.set_metadata("r_min_pervious", content.simulation_params.r_min_pervious)
    profiler.set_metadata(
        "r_min_impervious", content.simulation_params.r_min_impervious
    )
    profiler.update_metadata(metadata)

    project_box = load_project_box(
        content.project_box,
        content.stratigraphy,
        content.compute_resolution,
        content.voxels,
        content.voxels_units.root,
        content.is_base,
        content.simulation_params.r_min_pervious,
        content.simulation_params.r_min_impervious,
    )

    dem = Surface.from_dem_grid(
        content.surface_data,
        content.project_box.width,
        content.project_box.height,
    )

    # Create pykarstnsim Spring objects from the input springs
    springs = [
        Spring(
            origin=(s.x, s.y, s.z),
            index=i + 1,
            water_table_index=0,
            radius=0.0,
        )
        for i, s in enumerate(content.springs)
    ]

    water_tables = load_water_tables(
        content.voxels,
        content.project_box,
    )

    ordered_gwb_ids = sorted(water_tables.keys())

    ordered_water_tables = [water_tables[gwb_id] for gwb_id in ordered_gwb_ids]

    spring_to_wt_index = {
        gwb.spring_id: wt_index
        for wt_index, gwb_id in enumerate(
            ordered_gwb_ids,
            start=1,
        )
        for gwb in content.gwbs
        if gwb.gwb_id == gwb_id
    }

    for spring, input_spring in zip(
        springs,
        content.springs,
    ):
        if input_spring.poi_id not in spring_to_wt_index:
            raise ValueError(
                f"Spring {spring.index} has no associated groundwater body"
            )

        spring.water_table_index = spring_to_wt_index[input_spring.poi_id]

    faults = [
        Surface.from_vertices_and_triangles(
            f.vertices,
            f.triangles,
        )
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
        content.project_box.width / content.compute_resolution["x"],
        content.project_box.height / content.compute_resolution["y"],
        content.project_box.depth / content.compute_resolution["z"],
    )

    config = KarstConfig()
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

    start_step("run_simulation")
    result = run_simulation(
        config,
        project_box=project_box,
        sinks=sinks,
        springs=springs,
        connectivity_matrix=connectivity_matrix,
        water_tables=ordered_water_tables,
        topo_surface=dem,
        inception_surfaces=faults,
    )

    if result is None:
        raise ValueError("Simulation returned no result")

    profile_step("run_simulation")

    result_bytes = json.dumps(
        serialize_karstnsim_result(result),
        separators=(",", ":"),
    ).encode("utf-8")
    profiler.save_results()

    return result_bytes
