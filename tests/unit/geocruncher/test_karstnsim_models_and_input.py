import numpy as np
import pytest


@pytest.fixture(scope="session")
def karstnsim_content(
    karstnsim_data_dict,
    karstnsim_dem_bytes,
    karstnsim_voxels_str,
    karstnsim_fault_bytes,
):
    from geocruncher.computations import KarstNSimData
    from geocruncher.karstnsim.input import build_karstnsim_content

    data = KarstNSimData.model_validate(karstnsim_data_dict)

    return build_karstnsim_content(
        data,
        karstnsim_dem_bytes,
        karstnsim_voxels_str,
        karstnsim_fault_bytes,
    )


@pytest.fixture(scope="session")
def parsed_voxels(karstnsim_voxels_str):
    from geocruncher.karstnsim.input import load_voxels

    return load_voxels(karstnsim_voxels_str.splitlines())


@pytest.fixture(scope="session")
def parsed_faults(karstnsim_fault_bytes):
    from geocruncher.karstnsim.input import load_fault

    return {
        fault_id: load_fault(bytes) for fault_id, bytes in karstnsim_fault_bytes.items()
    }


######## Model Tests ########


class TestSimulationParameters:
    def test_camel_case_keys(self, karstnsim_data_dict):
        from geocruncher.karstnsim.models import SimulationParameters

        params = SimulationParameters.model_validate(
            karstnsim_data_dict["simulation_params"]
        )
        # check camelCase to snake_case mappings
        assert isinstance(params.seed, int)
        assert isinstance(params.k_pts, int)
        assert isinstance(params.cohesion_factor, float)
        assert isinstance(params.n_sinks, int)

    def test_auto_defaults(self):
        from geocruncher.karstnsim.models import SimulationParameters

        params = SimulationParameters()
        assert params.search_radius == "auto"
        assert params.max_inception_surface_distance == "auto"
        assert params.r_min_pervious == "auto"
        assert params.r_min_impervious == "auto"

    def test_numeric_overrides(self):
        from geocruncher.karstnsim.models import SimulationParameters

        params = SimulationParameters(search_radius=150.0, r_min_pervious=0.005)
        assert params.search_radius == 150.0
        assert params.r_min_pervious == 0.005


class TestKarstNSimProjectBox:
    def test_depth_property(self, karstnsim_data_dict):
        from geocruncher.karstnsim.models import KarstNSimProjectBox

        box = KarstNSimProjectBox.model_validate(karstnsim_data_dict["project_box"])
        assert box.depth == pytest.approx(box.max_elevation - box.min_elevation)

    def test_positive_dimensions(self, karstnsim_data_dict):
        from geocruncher.karstnsim.models import KarstNSimProjectBox

        box = KarstNSimProjectBox.model_validate(karstnsim_data_dict["project_box"])
        assert box.width > 0
        assert box.height > 0
        assert box.depth > 0


class TestKarstNSimGeologicalUnit:
    def test_all_permeability_values_valid(self, karstnsim_data_dict):
        from geocruncher.karstnsim.models import KarstNSimGeologicalUnit, Permeability

        for raw in karstnsim_data_dict["stratigraphy"]:
            unit = KarstNSimGeologicalUnit.model_validate(raw)
            assert isinstance(unit.permeability, Permeability)


class TestKarstNSimData:
    def test_full_round_trip(self, karstnsim_data_dict):
        from geocruncher.computations import KarstNSimData

        data = KarstNSimData.model_validate(karstnsim_data_dict)
        assert len(data.stratigraphy) > 0
        assert len(data.gwbs) > 0
        assert len(data.fault_ids) > 0
        assert len(data.springs) > 0
        assert len(data.voxels_units) > 0

    def test_springs_are_karstnsim_springs(self, karstnsim_data_dict):
        from geocruncher.computations import KarstNSimData
        from geocruncher.karstnsim.models import KarstNSimSpring

        data = KarstNSimData.model_validate(karstnsim_data_dict)

        for s in data.springs:
            assert isinstance(s, KarstNSimSpring)
            assert not isinstance(s, dict)


######## Input parsing tests ########


class TestLoadVoxels:
    def test_parses_header_and_shape(self, karstnsim_voxels_str):
        from geocruncher.karstnsim.input import load_voxels

        header, voxels = load_voxels(karstnsim_voxels_str.splitlines())

        assert (header.nx, header.ny, header.nz) == (150, 100, 75)
        assert voxels.shape == (150, 100, 75, 2)
        assert voxels.dtype == np.int32

    def test_cell_count_matches_header(self, parsed_voxels):
        header, voxels = parsed_voxels
        assert voxels.size == header.nx * header.ny * header.nz * 2


class TestLoadFaultFromOff:
    def test_shape(self, parsed_faults):
        for fault_id, fault in parsed_faults.items():
            assert fault.vertices.ndim == 2 and fault.vertices.shape[1] == 3, (
                f"Fault {fault_id}: unexpected vertices shape {fault.vertices.shape}"
            )
            assert fault.triangles.ndim == 2 and fault.triangles.shape[1] == 3, (
                f"Fault {fault_id}: unexpected triangles shape {fault.triangles.shape}"
            )

    def test_dtypes(self, parsed_faults):
        for fault_id, fault in parsed_faults.items():
            assert fault.vertices.dtype == np.float64, (
                f"Fault {fault_id}: vertices dtype should be float64"
            )
            assert fault.triangles.dtype == np.int32, (
                f"Fault {fault_id}: triangles dtype should be int32"
            )

    def test_triangle_indices_in_range(self, parsed_faults):
        for fault_id, fault in parsed_faults.items():
            assert fault.triangles.min() >= 0
            assert fault.triangles.max() < len(fault.vertices), (
                f"Fault {fault_id}: triangle index out of vertex range"
            )


class TestBuildKarstNSimContent:
    def test_surface_data_shape(self, karstnsim_content):
        assert karstnsim_content.surface_data.ndim == 2
        assert karstnsim_content.surface_data.shape[0] >= 2
        assert karstnsim_content.surface_data.shape[1] >= 2

    def test_compute_resolution_matches_voxels(self, karstnsim_content, parsed_voxels):
        header, _ = parsed_voxels
        assert karstnsim_content.compute_resolution["x"] == header.nx
        assert karstnsim_content.compute_resolution["y"] == header.ny
        assert karstnsim_content.compute_resolution["z"] == header.nz

    def test_fault_count(self, karstnsim_content, karstnsim_fault_bytes):
        assert len(karstnsim_content.faults) == len(karstnsim_fault_bytes)

    def test_surface_resolution_positive(self, karstnsim_content):
        assert karstnsim_content.surface_resolution.x > 0
        assert karstnsim_content.surface_resolution.y > 0


########
# Coordinate tests - ensure all x/y coordinates are in local box coordinates, not absolute coordinates
########


class TestCoordinates:
    def test_springs_within_project_box(self, karstnsim_data_dict):
        from geocruncher.computations import KarstNSimData

        data = KarstNSimData.model_validate(karstnsim_data_dict)
        box = data.project_box
        for s in data.springs:
            assert 0 <= s.x <= box.width, (
                f"Spring {s.poi_id} x={s.x:.1f} outside [0, {box.width:.1f}] — offset missing?"
            )
            assert 0 <= s.y <= box.height, (
                f"Spring {s.poi_id} y={s.y:.1f} outside [0, {box.height:.1f}] — offset missing?"
            )

    def test_catchments_within_project_box(self, karstnsim_data_dict):
        from geocruncher.computations import KarstNSimData

        data = KarstNSimData.model_validate(karstnsim_data_dict)
        box = data.project_box
        for s in data.springs:
            for i, (cx, cy) in enumerate(s.catchment):
                assert 0 <= cx <= box.width, (
                    f"Spring {s.poi_id} catchment[{i}] x={cx:.1f} outside [0, {box.width:.1f}]"
                )
                assert 0 <= cy <= box.height, (
                    f"Spring {s.poi_id} catchment[{i}] y={cy:.1f} outside [0, {box.height:.1f}]"
                )

    def test_fault_vertices_within_project_box(
        self, karstnsim_data_dict, karstnsim_fault_bytes
    ):
        """Fault vertex x/y must be in local box coordinates."""
        from geocruncher.computations import KarstNSimData
        from geocruncher.karstnsim.input import load_fault

        data = KarstNSimData.model_validate(karstnsim_data_dict)
        box = data.project_box
        eps = 0.1  # float rounding tolerance
        for fault_id, bytes in karstnsim_fault_bytes.items():
            fault = load_fault(bytes)
            xs, ys = fault.vertices[:, 0], fault.vertices[:, 1]
            assert xs.min() >= -eps and xs.max() <= box.width + eps, (
                f"Fault {fault_id} x [{xs.min():.3f}, {xs.max():.3f}] outside [0, {box.width:.1f}]"
            )
            assert ys.min() >= -eps and ys.max() <= box.height + eps, (
                f"Fault {fault_id} y [{ys.min():.3f}, {ys.max():.3f}] outside [0, {box.height:.1f}]"
            )

    def test_springs_match_gwbs(self, karstnsim_data_dict):
        """Every gwb.spring_id must have a matching spring."""
        from geocruncher.computations import KarstNSimData

        data = KarstNSimData.model_validate(karstnsim_data_dict)
        spring_ids = {s.poi_id for s in data.springs}
        gwb_spring_ids = {g.spring_id for g in data.gwbs}
        missing = gwb_spring_ids - spring_ids
        assert not missing, (
            f"gwbs reference spring_id(s) {missing} with no matching spring — Spring backend sending incomplete data"
        )
