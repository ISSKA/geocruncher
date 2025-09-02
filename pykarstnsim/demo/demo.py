import logging

import pykarstnsim_core
from pykarstnsim.loaders import (
    load_box_with_properties,
    load_points,
    load_pointset_with_properties,
    load_previous_network,
    load_connectivity_matrix_py,
    load_line,
    load_surface,
    load_distribution
)
logging.basicConfig(level=logging.INFO)

from pathlib import Path

from pykarstnsim.config import KarstConfig

LOGGER = logging.getLogger(__name__)
# Instantiate config
CONFIG = KarstConfig()

params = pykarstnsim_core.GeologicalParameters()
# Establish output directory early so we can mirror C++ path logic
save_dir = Path("./tmp").resolve()
params.directoryname = str(save_dir)
# ensure output dir exists
save_dir.mkdir(parents=True, exist_ok=True)

# Load domain box & properties (propdensity / ikp) similar to C++ parse_inputs
project_box, box_props = load_box_with_properties(CONFIG.domain.resolve())
propdensity: list[float] = []
propikp: list[float] = []
if box_props:
    # Each element = list of property values. First -> density, second -> ikp if present
    for row in box_props:
        if len(row) >= 1:
            propdensity.append(row[0])
        if len(row) >= 2:
            propikp.append(row[1])
else:
    LOGGER.warning("No properties parsed from domain box; using placeholder density/IKP values.")
pykarstnsim_core.initializeRng([CONFIG.selected_seed])

"""Phase 1: Load all raw geometry + properties + connectivity BEFORE creating KarsticNetwork.
After network creation we will not mutate or read the external 'params' object again (it is copied internally).
"""
_sinks_pts = load_points(CONFIG.sinks.resolve()) if CONFIG.sinks else []
_springs_pts = load_points(CONFIG.springs.resolve()) if CONFIG.springs else []

_sinks_pts, _sinks_props = load_pointset_with_properties(CONFIG.sinks.resolve()) if CONFIG.sinks else ([], [])
propsinksindex: list[int] = []
propsinksorder: list[int] = []
propsinksradius: list[float] = []
for prop in _sinks_props:
    # Expect columns: index order radius (already trimmed by loader). If radius absent, treat as 0.
    if not prop:
        continue
    if len(prop) >= 1:
        try:
            propsinksindex.append(int(prop[0]))
        except ValueError:
            propsinksindex.append(len(propsinksindex)+1)
    if len(prop) >= 2:
        try:
            propsinksorder.append(int(prop[1]))
        except ValueError:
            propsinksorder.append(1)
    else:
        propsinksorder.append(1)
    if CONFIG.use_sinks_radius:
        radius_val = 0.0
        if len(prop) >= 3:
            try:
                radius_val = float(prop[2])
            except ValueError:
                radius_val = 0.0
        propsinksradius.append(radius_val)
if not propsinksindex and _sinks_pts:
    # Fallback: assume sequential indices 1..N
    propsinksindex = list(range(1, len(_sinks_pts)+1))
if not propsinksorder and _sinks_pts:
    propsinksorder = [1]*len(_sinks_pts)
if CONFIG.use_sinks_radius and propsinksradius and len(propsinksradius) != len(_sinks_pts):
    LOGGER.warning("Some sink radii missing; not all sinks have a radius property.")
if CONFIG.use_sinks_radius and not propsinksradius:
    LOGGER.warning("Sinks radius usage enabled but no radius values found; radii list empty.")
_springs_pts_full, _springs_props = load_pointset_with_properties(CONFIG.springs.resolve()) if CONFIG.springs else ([], [])
propspringsindex: list[int] = []
propspringswtindex: list[int] = []
propspringsradius: list[float] = []
for prop in _springs_props:
    if not prop:
        continue
    if len(prop) >= 1:
        try:
            propspringsindex.append(int(prop[0]))
        except ValueError:
            propspringsindex.append(len(propspringsindex)+1)
    if len(prop) >= 2:
        try:
            propspringswtindex.append(int(prop[1]))
        except ValueError:
            propspringswtindex.append(1)
    else:
        propspringswtindex.append(1)
    if CONFIG.use_springs_radius:
        radius_val = 0.0
        if len(prop) >= 3:
            try:
                radius_val = float(prop[2])
            except ValueError:
                radius_val = 0.0
        propspringsradius.append(radius_val)
if not propspringsindex and _springs_pts_full:
    propspringsindex = list(range(1, len(_springs_pts_full)+1))
if not propspringswtindex and _springs_pts_full:
    propspringswtindex = [1]*len(_springs_pts_full)
if CONFIG.use_springs_radius and propspringsradius and len(propspringsradius) != len(_springs_pts_full):
    LOGGER.warning("Some spring radii missing; not all springs have a radius property.")
if CONFIG.use_springs_radius and not propspringsradius:
    LOGGER.warning("Springs radius usage enabled but no radius values found; radii list empty.")

# Connectivity matrix (must match raw sinks/springs counts); set BEFORE network creation
pre_conn_matrix = []
try:
    matrix_path = CONFIG.connectivity_matrix.resolve()
    if matrix_path.exists():
        pre_conn_matrix = load_connectivity_matrix_py(_sinks_pts, _springs_pts, matrix_path, pad_value=1)
    elif _sinks_pts and _springs_pts:
        pre_conn_matrix = [[1 for _ in range(len(_springs_pts))] for _ in range(len(_sinks_pts))]
        LOGGER.warning(f"Connectivity matrix file not found at {matrix_path}; using all-1 default matrix {len(_sinks_pts)}x{len(_springs_pts)} (pre-network).")
    if pre_conn_matrix:
        params.set_connectivity_matrix(pre_conn_matrix)
except Exception as e:
    LOGGER.error(f"Failed preparing connectivity matrix early: {e}")

# Water tables
water_tables = [load_surface(p.resolve()) for p in CONFIG.surf_wat_table]
# Keypoints
# TODO: what do these correspond to?
keypoints: list[pykarstnsim_core.KeyPoint] = []

### Phase 2: Create network and push sinks/springs (internal params copy takes initial matrix)
karst = pykarstnsim_core.KarsticNetwork(
    karstic_network_name=CONFIG.karstic_network_name,
    box=project_box,
    params=params,
    keypoints=keypoints,
    water_tables=water_tables
)
karst.set_save_directory(str(save_dir))
karst.set_sinks(_sinks_pts, propsinksindex, propsinksorder, CONFIG.use_sinks_radius, propsinksradius)
karst.set_springs(_springs_pts_full, propspringsindex, CONFIG.allow_single_outlet_connection, CONFIG.use_springs_radius, propspringsradius, propspringswtindex)

# Drop external reference to discourage further use (avoid confusion with internal copy)
params = None

if CONFIG.use_waypoints:
    _way_pts, _way_props = load_pointset_with_properties(CONFIG.waypoints.resolve())
    waypoints_impact_radius = [float(p[0]) for p in _way_props if p]
    waypoints_radius = [float(p[1]) for p in _way_props if CONFIG.use_waypoints_radius and len(p) >= 2]
    if CONFIG.use_waypoints_radius and waypoints_radius and len(waypoints_radius) != len(_way_pts):
        LOGGER.warning("Some waypoint radii missing; not all waypoints have a radius property.")
    if CONFIG.use_waypoints_radius and not waypoints_radius:
        LOGGER.warning("Waypoint radius usage enabled but no waypoint radii found.")
    karst.set_waypoints(
        waypoints=_way_pts,
        use_radius=CONFIG.use_waypoints_radius,
        radii=waypoints_radius,
        impact_radii=waypoints_impact_radius,
        weight=CONFIG.waypoints_weight,
    )
if CONFIG.use_deadend_points:
    karst.set_deadend_points(
        nb_deadend_points=CONFIG.nb_deadend_points,
        max_distance=float(CONFIG.max_distance_of_deadend_pts),
    )
if CONFIG.use_previous_networks:
    karst.set_previous_networks(
        previous_lines=[load_previous_network(p.resolve()) for p in CONFIG.previous_networks]
    )
if CONFIG.use_karstification_potential:
    karst.set_karstification_potential_parameters(
        weight=CONFIG.karstification_potential_weight,
    )
    if CONFIG.use_ghostrocks:
        karst.set_ghost_rocks(
            grid=project_box,
            ikp=propikp,  # mutate IKP in place like C++
            alteration_lines=load_line(CONFIG.alteration_lines.resolve()),
            interpolate_lines=CONFIG.interpolate_lines,
            ghostrock_max_vertical_size=float(CONFIG.ghostrock_max_vertical_size),
            use_max_depth_constraint=CONFIG.use_max_depth_constraint,
            ghost_rock_weight=float(CONFIG.ghost_rock_weight),
            max_depth_horizon=load_surface(CONFIG.max_depth_horizon.resolve()),
            ghostrock_width=float(CONFIG.ghostrock_width)
        )

if not CONFIG.sections_simulation_only:
    karst.set_wt_surfaces_sampling(
        network_name=CONFIG.karstic_network_name,
        water_table_surfaces=water_tables,
        refine=CONFIG.refine_surface_sampling,
    )

    if CONFIG.add_inception_surfaces:
        inception_surfaces_objs = [load_surface(p.resolve()) for p in CONFIG.inception_surfaces]
        if not CONFIG.use_sampling_points:  # corrected inversion
            karst.set_inception_surfaces_sampling(
                network_name=CONFIG.karstic_network_name,
                surfaces=inception_surfaces_objs,
                refine=CONFIG.refine_surface_sampling,
                create_vset_sampling=CONFIG.create_vset_sampling
            )
        else:
            LOGGER.info("Skipping inception surface sampling (use_sampling_points=True) to mirror C++ logic.")
        karst.safe_set_inception_horizons_parameters(
            horizons=inception_surfaces_objs,
            weight=CONFIG.inception_surface_constraint_weight,
        )
    else:
        karst.disable_inception_horizon()

    # Load and pass topographic surface via safe lifetime-preserving API
    _topo_surface_obj = load_surface(CONFIG.topo_surface.resolve())
    karst.safe_set_topo_surface(topographic_surface=_topo_surface_obj)

    if CONFIG.use_fracture_constraints:
        karst.set_fracture_constraint_parameters(
            orientations=CONFIG.fracture_families_orientations,
            tolerances=CONFIG.fracture_families_tolerance,
            weight=CONFIG.fracture_constraint_weight,
        )
    else:
        karst.disable_fractures()

    if CONFIG.use_no_karst_spheres:
        sphere_centers_pts, sphere_props = load_pointset_with_properties(CONFIG.sphere_centers.resolve())
        sphere_radii = [float(p[0]) for p in sphere_props if p]
        if not sphere_radii:
            LOGGER.warning("No sphere radii parsed; using fallback radius 5.0 for all no-karst spheres.")
        karst.set_no_karst_spheres_parameters(
            centers=sphere_centers_pts,
            radii=sphere_radii if sphere_radii else [5.0]
        )
    if CONFIG.use_cycle_amplification:
        karst.set_amplification_params(
            max_distance=float(CONFIG.max_distance_amplification),
            min_distance=float(CONFIG.min_distance_amplification),
            nb_cycles=int(CONFIG.nb_cycles)
    )
    karst.set_water_table_weight(
        vadose_weight=CONFIG.water_table_constraint_weight_vadose,
        phreatic_weight=CONFIG.water_table_constraint_weight_phreatic
    )
    karst.set_simulation_parameters(
        nghb_count=CONFIG.nghb_count,
        use_max_nghb_radius=CONFIG.use_max_nghb_radius,
        nghb_radius=CONFIG.nghb_radius,
        poisson_radius=CONFIG.poisson_radius,
        gamma=CONFIG.gamma,
        multiply_costs=CONFIG.multiply_costs,
        vadose_cohesion=CONFIG.vadose_cohesion,
    )
    # (Connectivity matrix already embedded in network's internal params copy from pre-network stage)

if CONFIG.simulate_sections:
    # Populate GeostatParams mirroring parse_inputs.cpp mapping
    geo = pykarstnsim_core.GeostatParams()
    geo.is_used = True
    geo.simulation_distribution = load_distribution(CONFIG.simulation_distribution.resolve())
    geo.global_vario_range = CONFIG.global_vario_range
    geo.global_range_of_neighborhood = CONFIG.global_range_of_neighborhood
    geo.global_vario_sill = CONFIG.global_vario_sill
    geo.global_vario_nugget = CONFIG.global_vario_nugget
    geo.global_vario_model = CONFIG.global_vario_model
    geo.interbranch_vario_range = CONFIG.interbranch_vario_range
    geo.interbranch_range_of_neighborhood = CONFIG.interbranch_range_of_neighborhood
    geo.interbranch_vario_sill = CONFIG.interbranch_vario_sill
    geo.interbranch_vario_nugget = CONFIG.interbranch_vario_nugget
    geo.interbranch_vario_model = CONFIG.interbranch_vario_model
    geo.intrabranch_vario_range = CONFIG.intrabranch_vario_range
    geo.intrabranch_range_of_neighborhood = CONFIG.intrabranch_range_of_neighborhood
    geo.intrabranch_vario_sill = CONFIG.intrabranch_vario_sill
    geo.intrabranch_vario_nugget = CONFIG.intrabranch_vario_nugget
    geo.intrabranch_vario_model = CONFIG.intrabranch_vario_model
    geo.number_max_of_neighborhood_points = CONFIG.number_max_of_neighborhood_points
    geo.nb_points_interbranch = CONFIG.nb_points_interbranch
    geo.proportion_interbranch = CONFIG.proportion_interbranch
    karst.set_geostat_params(geostat_params=geo)

karst.set_noise_parameters(
    use_noise=CONFIG.use_noise,
    use_noise_on_all=CONFIG.use_noise_on_all,
    frequency=CONFIG.noise_frequency,
    octaves=CONFIG.noise_octaves,
    noise_weight=float(CONFIG.noise_weight)
)

sampling_points: list[pykarstnsim_core.Vector3] = []

if CONFIG.use_density_property and not propdensity:
    LOGGER.warning("Density property requested but domain box provided none; placeholder values will be used.")
if CONFIG.use_karstification_potential and not propikp:
    LOGGER.warning("Karstification potential requested but IKP values missing; placeholder IKP values will be used.")

# Provide safe fallback arrays matching voxel count if properties are required but missing
nu = project_box.get_nu(); nv = project_box.get_nv(); nw = project_box.get_nw()
cell_count = max(1, nu * nv * nw)
run_propdensity = propdensity
run_propikp = propikp
if CONFIG.use_density_property and not run_propdensity:
    LOGGER.warning("Density property requested but domain box provided none; placeholder values will be used.")
    run_propdensity = [1.0] * cell_count
if CONFIG.use_karstification_potential and not run_propikp:
    LOGGER.warning("Karstification potential requested but IKP values missing; placeholder IKP values will be used.")
    run_propikp = [1.0] * cell_count

LOGGER.info("Starting simulation, will output to %s", save_dir)
res = karst.run_simulation(
    sections_simulation_only=CONFIG.sections_simulation_only,
    create_nghb_graph=CONFIG.create_nghb_graph,
    create_nghb_graph_property=CONFIG.create_nghb_graph_property,
    use_amplification=CONFIG.use_cycle_amplification,
    use_sampling_points=CONFIG.use_sampling_points,
    fraction_karst_perm=CONFIG.fraction_karst_perm,
    fraction_old_karst_perm=CONFIG.fraction_old_karst_perm,
    max_inception_surface_distance=CONFIG.max_inception_surface_distance,
    sampling_points=sampling_points,
    create_vset_sampling=CONFIG.create_vset_sampling,
    use_density_property=CONFIG.use_density_property,
    k_pts=CONFIG.k_pts,
    propdensity=run_propdensity,
    propikp=run_propikp
)


print("Simulation result:", res)
