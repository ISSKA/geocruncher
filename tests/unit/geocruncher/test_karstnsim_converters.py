import numpy as np
import pytest
from pykarstnsim.models import ConnectivityType

from geocruncher.karstnsim.converters import (
    load_project_box,
    load_sinks,
    load_water_tables,
)
from geocruncher.karstnsim.models import (
    GeologicalUnitInput,
    ProjectBoxInput,
    SpringInput,
    StratigraphyInput,
)

pytestmark = pytest.mark.skipif(
    not pytest.importorskip("pykarstnsim", reason="pykarstnsim not installed"),
    reason="pykarstnsim not installed",
)


######## load_project_box tests ########


def test_densities_reflect_permeability():
    box = ProjectBoxInput.model_validate(
        {"width": 10.0, "height": 10.0, "min_elevation": 0.0, "max_elevation": 30.0}
    )
    stratigraphy = StratigraphyInput(
        [
            GeologicalUnitInput.model_validate(
                {"name": "Aquifer", "permeability": "Karstified", "strati_unit_id": 1}
            ),
            GeologicalUnitInput.model_validate(
                {
                    "name": "Impervious",
                    "permeability": "NonKarstified",
                    "strati_unit_id": 2,
                }
            ),
        ]
    )
    # z=0: rank 1 (karstified), z=1: rank 2 (non-karstified)
    voxels = np.array([[[[1, 0], [2, 0]]]], dtype=np.int32)

    result = load_project_box(
        box, stratigraphy, {"x": 1, "y": 1, "z": 2}, voxels, [1, 2]
    )

    base_density = 2 / 30.0
    sparse_density = base_density * 2
    densities = result.density

    assert densities[0] == pytest.approx(base_density)  # karstified → potential > 0
    assert densities[1] == pytest.approx(
        sparse_density
    )  # non-karstified → potential == 0


def test_potentials_gwb_cells_are_one():
    """Cells inside a GWB (gwb_id > 0) must have potential 1.0 regardless of rank."""
    box = ProjectBoxInput.model_validate(
        {"width": 10.0, "height": 10.0, "min_elevation": 0.0, "max_elevation": 20.0}
    )
    stratigraphy = StratigraphyInput(
        [
            GeologicalUnitInput.model_validate(
                {"name": "Aquifer", "permeability": "Karstified", "strati_unit_id": 1}
            )
        ]
    )
    # z=0: rank 1, gwb 0 (not in gwb); z=1: rank 1, gwb 5 (in gwb)
    voxels = np.array([[[[1, 0], [1, 5]]]], dtype=np.int32)

    result = load_project_box(box, stratigraphy, {"x": 1, "y": 1, "z": 2}, voxels, [1])

    potentials = result.karstification_potential
    assert potentials[0] == pytest.approx(0.5)  # not in gwb
    assert potentials[1] == pytest.approx(1.0)  # in gwb


def test_raises_when_density_exceeds_one():
    """cells_w / depth > 1 must raise to avoid invalid density values."""
    box = ProjectBoxInput.model_validate(
        {"width": 10.0, "height": 10.0, "min_elevation": 0.0, "max_elevation": 5.0}
    )
    stratigraphy = StratigraphyInput(
        [
            GeologicalUnitInput.model_validate(
                {"name": "Aquifer", "permeability": "Karstified", "strati_unit_id": 1}
            )
        ]
    )
    voxels = np.array([[[[1, 0]] * 10]], dtype=np.int32).reshape(1, 1, 10, 2)

    with pytest.raises(ValueError, match="density"):
        load_project_box(box, stratigraphy, {"x": 1, "y": 1, "z": 10}, voxels, [1])


######## load_sinks tests ########


def test_sinks_land_inside_catchment_polygon():
    """All generated sink XY coordinates must be within the spring's catchment polygon."""
    springs = [
        SpringInput(
            poi_id=1,
            x=5.0,
            y=5.0,
            z=1.0,
            catchment=[(2.0, 2.0), (2.0, 8.0), (8.0, 8.0), (8.0, 2.0)],
        )
    ]
    surface = np.full((11, 11), 100.0, dtype=np.float64)
    rng = np.random.default_rng(42)

    sinks, _ = load_sinks(
        10,
        springs,
        {"x": 11, "y": 11},
        {"x": 1.0, "y": 1.0},
        surface,
        rng,
        1,
    )

    assert len(sinks) == 10
    for sink in sinks:
        x, y = sink.origin.x, sink.origin.y
        assert 2.0 <= x <= 8.0
        assert 2.0 <= y <= 8.0


def test_sink_elevation_matches_surface():
    """Sink z must equal the elevation given by the bilinear interpolation at its XY."""
    # Flat surface at known elevation
    surface = np.full((11, 11), 250.0, dtype=np.float64)
    springs = [
        SpringInput(
            poi_id=1,
            x=5.0,
            y=5.0,
            z=1.0,
            catchment=[(2.0, 2.0), (2.0, 8.0), (8.0, 8.0), (8.0, 2.0)],
        )
    ]
    rng = np.random.default_rng(0)

    sinks, _ = load_sinks(
        5,
        springs,
        {"x": 11, "y": 11},
        {"x": 1.0, "y": 1.0},
        surface,
        rng,
        1,
    )

    for sink in sinks:
        assert sink.origin.z == pytest.approx(250.0)


def test_connectivity_matrix_links_sink_to_correct_spring():
    """Each sink must be connected to exactly one spring, and be inside its catchment polygon."""
    springs = [
        SpringInput(
            poi_id=1,
            x=5.0,
            y=5.0,
            z=1.0,
            catchment=[(2.0, 2.0), (2.0, 8.0), (8.0, 8.0), (8.0, 2.0)],
        ),
        SpringInput(
            poi_id=2,
            x=7.0,
            y=7.0,
            z=1.0,
            catchment=[(5.0, 5.0), (5.0, 9.0), (9.0, 9.0), (9.0, 5.0)],
        ),
    ]
    surface = np.full((11, 11), 100.0, dtype=np.float64)
    rng = np.random.default_rng(0)

    sinks, connectivity = load_sinks(
        4,
        springs,
        {"x": 11, "y": 11},
        {"x": 1.0, "y": 1.0},
        surface,
        rng,
        2,
    )

    catchments = [springs[0].catchment, springs[1].catchment]

    for i, sink in enumerate(sinks):
        row = connectivity.matrix[i]
        connected = [j for j, v in enumerate(row) if v == ConnectivityType.CONNECTED]
        assert len(connected) == 1

        spring_idx = connected[0]
        x, y = sink.origin.x, sink.origin.y
        coords = catchments[spring_idx]
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        assert min(xs) <= x <= max(xs)
        assert min(ys) <= y <= max(ys)


######## load_water_tables tests ########


def test_vertex_z_coords_match_voxel_top_layer():
    """Z coordinates of surface vertices must equal (top_layer_index + 1) * dz + min_elevation."""
    box = ProjectBoxInput.model_validate(
        {
            "width": 10.0,
            "height": 10.0,
            "min_elevation": 100.0,
            "max_elevation": 130.0,
        }
    )
    # 3x3x3 grid, gwb_id=1 only at z=2 (top layer) for all XY
    voxels = np.zeros((3, 3, 3, 2), dtype=np.int32)
    voxels[:, :, 2, 1] = 1

    surfaces = load_water_tables(voxels, box)

    dz = 30.0 / 3  # depth / nz
    expected_z = (2 + 1) * dz + 100.0  # top_layer=2
    assert 1 in surfaces
    surface = surfaces[1]
    z_coords = [
        surface.surface.get_node(i).z for i in range(surface.surface.get_nb_pts())
    ]
    assert np.allclose(z_coords, expected_z)


def test_each_gwb_produces_separate_surface():
    """Distinct gwb_ids in the voxel array must produce distinct surfaces."""
    box = ProjectBoxInput.model_validate(
        {"width": 10.0, "height": 10.0, "min_elevation": 0.0, "max_elevation": 20.0}
    )
    voxels = np.zeros((4, 4, 2, 2), dtype=np.int32)
    voxels[:2, :, 1, 1] = 1  # gwb 1 in left half
    voxels[2:, :, 1, 1] = 2  # gwb 2 in right half

    surfaces = load_water_tables(voxels, box)

    assert set(surfaces.keys()) == {1, 2}

    xs1 = {
        surfaces[1].surface.get_node(i).x
        for i in range(surfaces[1].surface.get_nb_pts())
    }
    xs2 = {
        surfaces[2].surface.get_node(i).x
        for i in range(surfaces[2].surface.get_nb_pts())
    }
    assert xs1.isdisjoint(xs2)


def test_gwb_zero_is_excluded():
    """Voxels with gwb_id=0 must not produce a surface."""
    box = ProjectBoxInput.model_validate(
        {"width": 10.0, "height": 10.0, "min_elevation": 0.0, "max_elevation": 10.0}
    )
    voxels = np.zeros((2, 2, 2, 2), dtype=np.int32)  # all gwb_id=0

    surfaces = load_water_tables(voxels, box)

    assert surfaces == {}
