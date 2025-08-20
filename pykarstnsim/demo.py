import pykarstnsim

network_name = "Test"

# Config
use_waypoints = False
use_deadend_points = False
use_previous_networks = False
use_karstification_potential = False
use_ghostrocks = False
sections_simulation_only = False
add_inception_surface = False
use_sampling_points = False
use_fracture_constraints = False
use_no_karst_spheres = False
use_amplification = False
simulate_sections = False

params = pykarstnsim.GeologicalParameters()
project_box = pykarstnsim.Box()
keypoints: list[pykarstnsim.KeyPoint] = []
water_tables: list[pykarstnsim.Surface] = []

pykarstnsim.initializeRng([21])

karst = pykarstnsim.KarsticNetwork(
    karstic_network_name=network_name,
    box=project_box,
    params=params,
    keypoints=keypoints,
    water_tables=water_tables
)
karst.set_save_directory("./tmp")

karst.set_sinks(
    sinks=[],
    indices=[],
    order=[],
    use_radius=True,
    radii=[]
)
karst.set_springs(
    springs=[],
    indices=[],
    allow_single_outlet=True,
    use_radius=True,
    radii=[],
    water_table_indices=[]
)
if use_waypoints:
    karst.set_waypoints(
        waypoints=[],
        use_radius=True,
        radii=[],
        impact_radii=[],
        weight=1.0,
    )
if use_deadend_points:
    karst.set_deadend_points(
        nb_deadend_points=0,
        max_distance=0.0,
    )
if use_previous_networks:
    karst.set_previous_networks(
        previous_lines=[]
    )
if use_karstification_potential:
    karst.set_karstification_potential_parameters(
        weight=1.0,
    )
    if use_ghostrocks:
        # ghost rocks need karstification potential
        karst.set_ghost_rocks(
            grid=pykarstnsim.Box(),
            ikp=[],
            alteration_lines=pykarstnsim.Line(),
            interpolate_lines=False,
            ghostrock_max_vertical_size=0.0,
            use_max_depth_constraint=False,
            ghost_rock_weight=1.0,
            max_depth_horizon=pykarstnsim.Surface(),
            ghostrock_width=1.0
        )

# IF !sections_simulation_only
karst.set_wt_surfaces_sampling(
    network_name=network_name,
    water_table_surfaces=water_tables,
    refine=0
)

if add_inception_surface:
    if use_sampling_points:
        karst.set_inception_surfaces_sampling(
            network_name=network_name,
            surfaces=[],
            refine=0,
            create_vset_sampling=False
        )
    karst.set_inception_horizons_parameters(
        horizons=[],
        weight=1.0,
    )
else:
    karst.disable_inception_horizon()

karst.set_topo_surface(
    topographic_surface=pykarstnsim.Surface(),
)

if use_fracture_constraints:
    karst.set_fracture_constraint_parameters(
        orientations=[],
        tolerances=[],
        weight=1.0,
    )
else:
    karst.disable_fractures()

if use_no_karst_spheres:
    karst.set_no_karst_spheres_parameters(
        centers=[],
        radii=[]
    )
if use_amplification:
    karst.set_amplification_params(
        max_distance=1.0,
        min_distance=0.1,
        nb_cycles=10
    )
karst.set_water_table_weight(
    vadose_weight=1.0,
    phreatic_weight=1.0
)
karst.set_simulation_parameters(
    nghb_count=1,
    use_max_nghb_radius=True,
    nghb_radius=21.0,
    poisson_radius=10.0,
    gamma=10.0,
    multiply_costs=True,
    vadose_cohesion=True,
)
karst.read_connectivity_matrix(
    sinks=[],
    springs=[]
)

if simulate_sections:
    karst.set_geostat_params(geostat_params=pykarstnsim.GeostatParams())

karst.set_noise_parameters(
    use_noise=True,
    use_noise_on_all=False,
    frequency=10,
    octaves=10,
    noise_weight=1.0
)

sampling_points: list[pykarstnsim.Vector3] = []

res = karst.run_simulation(
    sections_simulation_only=sections_simulation_only,
    create_nghb_graph=False,
    create_nghb_graph_property=False,
    use_amplification=use_amplification,
    use_sampling_points=use_sampling_points,
    fraction_karst_perm=0.5,
    fraction_old_karst_perm=0.5,
    max_inception_surface_distance=0.5,
    sampling_points=sampling_points,
    create_vset_sampling=False,
    use_density_property=True,
    k_pts=10,
    propdensity=[1.0, 1.0,],
    propikp=[1.0, 1.0,]
)

print("Simulation result:", res)
