import logging
import signal
import typing

import pykarstnsim_core

from pykarstnsim.config import KarstConfig
from pykarstnsim.models import (
    ConnectivityMatrix,
    ProjectBox,
    Sink,
    Spring,
    Surface,
    Waypoint,
)

LOGGER = logging.getLogger(__name__)


def run_simulation(
    config: KarstConfig,
    project_box: ProjectBox,
    sinks: list[Sink],
    springs: list[Spring],
    connectivity_matrix: ConnectivityMatrix,
    water_tables: list[Surface],
    topo_surface: Surface,
    inception_surfaces: list[Surface] = [],
    waypoints: list[Waypoint] = [],
    sampling_points: list[pykarstnsim_core.Vector3] = [],
    previous_networks: list[pykarstnsim_core.Line] = [],
) -> typing.Optional[pykarstnsim_core.KarstNetworkResult]:
    params = pykarstnsim_core.GeologicalParameters()

    # set seed to ensure reproducibility
    pykarstnsim_core.initializeRng([config.selected_seed])

    params.set_connectivity_matrix(connectivity_matrix.matrix)

    # Keypoints
    # TODO: what do these correspond to?
    keypoints: list[pykarstnsim_core.KeyPoint] = []

    ### Phase 2: Create network and push sinks/springs (internal params copy takes initial matrix)
    karst = pykarstnsim_core.KarsticNetwork(
        karstic_network_name=config.karstic_network_name,
        box=project_box.as_box(),
        params=params,
        keypoints=keypoints,
        water_tables=[water_table.as_surface() for water_table in water_tables],
    )
    karst.set_sinks(
        sinks=[s.origin for s in sinks],
        indices=[s.index for s in sinks],
        order=[s.order for s in sinks],
        use_radius=config.use_sinks_radius,
        radii=[s.radius for s in sinks],
    )
    karst.set_springs(
        springs=[s.origin for s in springs],
        indices=[s.index for s in springs],
        allow_single_outlet=config.allow_single_outlet_connection,
        use_radius=config.use_springs_radius,
        radii=[s.radius for s in springs],
        water_table_indices=[s.water_table_index for s in springs],
    )

    # Drop external reference to discourage further use (avoid confusion with internal copy)
    params = None

    if len(waypoints) > 0:
        radii: list[float] = []
        impact_radii: list[float] = []
        for wp in waypoints:
            if wp.radius is not None:
                radii.append(wp.radius)
            if wp.impact_radius is not None:
                impact_radii.append(wp.impact_radius)
        # sanity check
        if (len(radii) > 0 and len(radii) != len(waypoints)) or (
            len(impact_radii) > 0 and len(impact_radii) != len(waypoints)
        ):
            raise ValueError(
                "Waypoint radius or impact_radius list length does not match number of waypoints."
            )
        karst.set_waypoints(
            waypoints=[wp.origin for wp in waypoints],
            use_radius=len(radii) > 0,
            radii=radii,
            impact_radii=impact_radii,
            weight=config.waypoints_weight,
        )
    if config.nb_deadend_points > 0:
        karst.set_deadend_points(
            nb_deadend_points=config.nb_deadend_points,
            max_distance=config.max_distance_of_deadend_pts,
        )
    if len(previous_networks) > 0:
        karst.set_previous_networks(previous_lines=previous_networks)

    if config.karstification_potential_weight > 0:
        karst.set_karstification_potential_parameters(
            weight=config.karstification_potential_weight
        )
        if config.use_ghostrocks:
            # TODO: add support for ghost rocks in Python interface
            pass

    karst.set_wt_surfaces_sampling(
        network_name=config.karstic_network_name,
        water_table_surfaces=[wt.as_surface() for wt in water_tables],
        refine=config.refine_surface_sampling,
    )

    if len(inception_surfaces) > 0:
        if not config.use_sampling_points:
            # TODO add support for sampling points in Python interface
            pass

        karst.set_inception_horizons_parameters(
            horizons=[surf.as_surface() for surf in inception_surfaces],
            weight=config.inception_surface_constraint_weight,
        )
    else:
        karst.disable_inception_horizon()

    karst.set_topo_surface(
        topographic_surface=topo_surface.as_surface(),
    )

    if config.use_fracture_constraints:
        karst.set_fracture_constraint_parameters(
            orientations=config.fracture_families_orientations,
            tolerances=config.fracture_families_tolerance,
            weight=config.fracture_constraint_weight,
        )
    else:
        karst.disable_fractures()

    # TODO: add support for no-karst spheres in Python interface

    if config.use_cycle_amplification:
        karst.set_amplification_params(
            max_distance=config.max_distance_amplification,
            min_distance=config.min_distance_amplification,
            nb_cycles=config.nb_cycles,
        )

    karst.set_water_table_weight(
        vadose_weight=config.water_table_constraint_weight_vadose,
        phreatic_weight=config.water_table_constraint_weight_phreatic,
    )

    karst.set_simulation_parameters(
        nghb_count=config.nghb_count,
        use_max_nghb_radius=config.use_max_nghb_radius,
        nghb_radius=config.nghb_radius,
        poisson_radius=config.poisson_radius,
        gamma=config.gamma,
        multiply_costs=config.multiply_costs,
        vadose_cohesion=config.vadose_cohesion,
    )

    if config.simulate_sections:
        # TODO: add support for sections simulation in Python interface
        pass

    karst.set_noise_parameters(
        use_noise=config.use_noise,
        use_noise_on_all=config.use_noise_on_all,
        frequency=config.noise_frequency,
        octaves=config.noise_octaves,
        noise_weight=config.noise_weight,
    )

    # allow Ctrl-C to interrupt simulation
    # see: https://stackoverflow.com/a/68441714
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    LOGGER.info("Starting karstification simulation...")
    with pykarstnsim_core.ostream_redirect():
        return karst.run_simulation(
            sections_simulation_only=False,
            create_nghb_graph=False,
            create_nghb_graph_property=False,
            create_solved_connectivity_matrix=False,
            use_amplification=config.use_cycle_amplification,
            use_sampling_points=len(sampling_points) > 0,
            fraction_karst_perm=config.fraction_karst_perm,
            fraction_old_karst_perm=config.fraction_old_karst_perm,
            max_inception_surface_distance=config.max_inception_surface_distance,
            sampling_points=sampling_points,
            create_vset_sampling=False,
            use_density_property=config.use_density_property,
            k_pts=config.k_pts,
            propdensity=project_box.density,
            propikp=project_box.karstification_potential,
        )
