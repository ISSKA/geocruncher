from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class KarstConfig:
    """Simulation configuration (now using pathlib.Path for file system entries)."""
    # Name & repository roots
    karstic_network_name: str = "example"

    # General parameters
    domain: Path = Path("Input_files/example_box.txt")
    selected_seed: int = 1
    number_of_iterations: int = 1
    vary_seed: bool = True
    topo_surface: Path = Path("Input_files/example_topo_surf.txt")

    # Sampling / density
    use_sampling_points: bool = False
    use_density_property: bool = True
    k_pts: int = 10
    poisson_radius: float = 0.01  # default from C++

    # N-N graph
    nghb_count: int = 100
    use_max_nghb_radius: bool = False
    nghb_radius: float = 0.0  # default in C++

    # Inlets / outlets / waypoints
    use_sinks_radius: bool = False
    sinks: Path = Path("Input_files/example_sinks.txt")
    use_springs_radius: bool = False
    springs: Path = Path("Input_files/example_springs.txt")
    allow_single_outlet_connection: bool = True
    use_waypoints: bool = False
    use_waypoints_radius: bool = False
    waypoints_weight: float = 0.1
    waypoints: Path = Path("Input_files/example_waypoints.txt")

    # Connectivity matrix file (full path like other loaders)
    connectivity_matrix: Path = Path("Input_files/connectivity_matrix.txt")

    # Ghost rocks
    use_ghostrocks: bool = False
    alteration_lines: Path = Path("Input_files/example_alteration_lines.txt")
    interpolate_lines: bool = False
    ghostrock_max_vertical_size: int = 110
    use_max_depth_constraint: bool = True
    ghost_rock_weight: int = 2
    max_depth_horizon: Path = Path("Input_files/example_inception_surf3.txt")
    ghostrock_width: int = 60

    # Inception surfaces
    add_inception_surfaces: bool = True
    refine_surface_sampling: int = 2
    inception_surfaces: list[Path] = field(default_factory=lambda: [
        Path("Input_files/example_inception_surf1.txt"),
        Path("Input_files/example_inception_surf2.txt"),
    ])
    inception_surface_constraint_weight: float = 1.0
    max_inception_surface_distance: float = 50.0

    # Karstification potential
    use_karstification_potential: bool = True
    karstification_potential_weight: float = 1.0

    # Fractures
    use_fracture_constraints: bool = True
    fracture_families_orientations: list[int] = field(default_factory=lambda: [0, 60])
    fracture_families_tolerance: list[int] = field(default_factory=lambda: [5, 5])
    fracture_constraint_weight: float = 0.5

    # Previous networks & sections
    use_previous_networks: bool = False
    previous_networks: list[Path] = field(default_factory=list)
    fraction_old_karst_perm: float = 0.5
    sections_simulation_only: bool = False

    # No-karst spheres
    use_no_karst_spheres: bool = False
    sphere_centers: Path = Path("Input_files/example_nokarstspheres.txt")

    # Water tables & weights
    surf_wat_table: list[Path] = field(default_factory=lambda: [
        Path("Input_files/example_watertable_surf1.txt"),
        Path("Input_files/example_watertable_surf2.txt"),
    ])
    water_table_constraint_weight_vadose: float = 1.0
    water_table_constraint_weight_phreatic: float = 1.0

    # Deadend points amplification
    use_deadend_points: bool = False
    nb_deadend_points: int = 15
    max_distance_of_deadend_pts: int = 50

    # Cycle amplification
    use_cycle_amplification: bool = False
    max_distance_amplification: int = 150
    min_distance_amplification: int = 50
    nb_cycles: int = 20

    # Noise parameters
    use_noise: bool = False
    use_noise_on_all: bool = False
    noise_frequency: int = 10
    noise_octaves: int = 1
    noise_weight: int = 10

    # Sections simulation
    simulate_sections: bool = False
    simulation_distribution: Path = Path("Input_files/eq_radius_initial_distrib.txt")
    global_vario_range: int = 50
    global_range_of_neighborhood: int = 150
    global_vario_sill: float = 0.92
    global_vario_nugget: float = 0.33
    global_vario_model: str = "Exponential"
    interbranch_vario_range: int = 30
    interbranch_range_of_neighborhood: int = 80
    interbranch_vario_sill: float = 0.92
    interbranch_vario_nugget: float = 0.34
    interbranch_vario_model: str = "Exponential"
    intrabranch_vario_range: int = 30
    intrabranch_range_of_neighborhood: int = 45
    intrabranch_vario_sill: float = 0.55
    intrabranch_vario_nugget: float = 0.31
    intrabranch_vario_model: str = "Exponential"
    number_max_of_neighborhood_points: int = 16
    nb_points_interbranch: int = 7
    proportion_interbranch: float = 0.1

    # Cost graph parameters
    gamma: float = 2.0
    fraction_karst_perm: float = 0.9
    vadose_cohesion: bool = True
    multiply_costs: bool = False

    # Save parameters
    create_vset_sampling: bool = False
    create_nghb_graph: bool = False
    create_nghb_graph_property: bool = False
    create_solved_connectivity_matrix: bool = False
    create_grid: bool = False
