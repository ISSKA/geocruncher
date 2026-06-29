import numpy as np
import pytest

######## Model Tests ########


class TestSimulationParameters:
    def test_camel_case_keys(self, karst_nsim_data_dict):
        from geocruncher.karst.models import SimulationParameters

        params = SimulationParameters.model_validate(
            karst_nsim_data_dict["simulation_params"]
        )
        # check camelCase to snake_case mappings
        assert isinstance(params.seed, int)
        assert isinstance(params.k_pts, int)
        assert isinstance(params.cohesion_factor, float)
        assert isinstance(params.n_sinks, int)

    def test_auto_defaults(self):
        from geocruncher.karst.models import SimulationParameters

        params = SimulationParameters()
        assert params.search_radius == "auto"
        assert params.max_inception_surface_distance == "auto"
        assert params.r_min_pervious == "auto"
        assert params.r_min_impervious == "auto"

    def test_numeric_overrides(self):
        from geocruncher.karst.models import SimulationParameters

        params = SimulationParameters(search_radius=150.0, r_min_pervious=0.005)
        assert params.search_radius == 150.0
        assert params.r_min_pervious == 0.005


class TestKarstProjectBox:
    def test_depth_property(self, karst_nsim_data_dict):
        from geocruncher.karst.models import KarstProjectBox

        box = KarstProjectBox.model_validate(karst_nsim_data_dict["project_box"])
        assert box.depth == pytest.approx(box.max_elevation - box.min_elevation)

    def test_positive_dimensions(self, karst_nsim_data_dict):
        from geocruncher.karst.models import KarstProjectBox

        box = KarstProjectBox.model_validate(karst_nsim_data_dict["project_box"])
        assert box.width > 0
        assert box.height > 0
        assert box.depth > 0


class TestKarstGeologicalUnit:
    def test_all_permeability_values_valid(self, karst_nsim_data_dict):
        from geocruncher.karst.models import KarstGeologicalUnit, Permeability

        for raw in karst_nsim_data_dict["stratigraphy"]:
            unit = KarstGeologicalUnit.model_validate(raw)
            assert isinstance(unit.permeability, Permeability)


class TestKarstNSimData:
    def test_full_round_trip(self, karst_nsim_data_dict):
        from geocruncher.computations import KarstNSimData

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        assert len(data.stratigraphy) > 0
        assert len(data.gwbs) > 0
        assert len(data.fault_ids) > 0
        assert len(data.springs) > 0
        assert len(data.voxels_units) > 0

    def test_springs_are_karst_springs(self, karst_nsim_data_dict):
        from geocruncher.computations import KarstNSimData
        from geocruncher.karst.models import KarstSpring

        data = KarstNSimData.model_validate(karst_nsim_data_dict)

        for s in data.springs:
            assert isinstance(s, KarstSpring)
            assert not isinstance(s, dict)


######## Input parsing tests ########


class TestLoadVoxels:
    def test_header_parsed(self, karst_voxels_str):
        from geocruncher.karst.input import load_voxels

        header, _ = load_voxels(karst_voxels_str.splitlines())
        assert header.nx > 0
        assert header.ny > 0
        assert header.nz > 0

    def test_array_shape(self, karst_voxels_str):
        from geocruncher.karst.input import load_voxels

        header, voxels = load_voxels(karst_voxels_str.splitlines())
        assert voxels.shape == (header.nx, header.ny, header.nz, 2)
        assert voxels.dtype == np.int32

    def test_cell_count_matches_header(self, karst_voxels_str):
        from geocruncher.karst.input import load_voxels

        header, voxels = load_voxels(karst_voxels_str.splitlines())
        assert voxels.size == header.nx * header.ny * header.nz * 2


class TestLoadFaultFromOff:
    def test_shape(self, karst_fault_off_bytes):
        from geocruncher.karst.input import load_fault_from_off

        for fault_id, off_bytes in karst_fault_off_bytes.items():
            fault = load_fault_from_off(off_bytes)
            assert fault.vertices.ndim == 2 and fault.vertices.shape[1] == 3, (
                f"Fault {fault_id}: unexpected vertices shape {fault.vertices.shape}"
            )
            assert fault.triangles.ndim == 2 and fault.triangles.shape[1] == 3, (
                f"Fault {fault_id}: unexpected triangles shape {fault.triangles.shape}"
            )

    def test_dtypes(self, karst_fault_off_bytes):
        from geocruncher.karst.input import load_fault_from_off

        for fault_id, off_bytes in karst_fault_off_bytes.items():
            fault = load_fault_from_off(off_bytes)
            assert fault.vertices.dtype == np.float32, (
                f"Fault {fault_id}: vertices dtype should be float32"
            )
            assert fault.triangles.dtype == np.int32, (
                f"Fault {fault_id}: triangles dtype should be int32"
            )

    def test_triangle_indices_in_range(self, karst_fault_off_bytes):
        from geocruncher.karst.input import load_fault_from_off

        for fault_id, off_bytes in karst_fault_off_bytes.items():
            fault = load_fault_from_off(off_bytes)
            assert fault.triangles.min() >= 0
            assert fault.triangles.max() < len(fault.vertices), (
                f"Fault {fault_id}: triangle index out of vertex range"
            )


class TestBuildKarstContent:
    def test_surface_data_shape(
        self,
        karst_nsim_data_dict,
        karst_dem_bytes,
        karst_voxels_str,
        karst_fault_off_bytes,
    ):
        from geocruncher.computations import KarstNSimData
        from geocruncher.karst.input import build_karst_content

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        content = build_karst_content(
            data, karst_dem_bytes, karst_voxels_str, karst_fault_off_bytes
        )
        assert content.surface_data.ndim == 2
        assert content.surface_data.shape[0] >= 2
        assert content.surface_data.shape[1] >= 2

    def test_compute_resolution_matches_voxels(
        self,
        karst_nsim_data_dict,
        karst_dem_bytes,
        karst_voxels_str,
        karst_fault_off_bytes,
    ):
        from geocruncher.computations import KarstNSimData
        from geocruncher.karst.input import build_karst_content, load_voxels

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        content = build_karst_content(
            data, karst_dem_bytes, karst_voxels_str, karst_fault_off_bytes
        )
        header, _ = load_voxels(karst_voxels_str.splitlines())
        assert content.compute_resolution["x"] == header.nx
        assert content.compute_resolution["y"] == header.ny
        assert content.compute_resolution["z"] == header.nz

    def test_fault_count(
        self,
        karst_nsim_data_dict,
        karst_dem_bytes,
        karst_voxels_str,
        karst_fault_off_bytes,
    ):
        from geocruncher.computations import KarstNSimData
        from geocruncher.karst.input import build_karst_content

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        content = build_karst_content(
            data, karst_dem_bytes, karst_voxels_str, karst_fault_off_bytes
        )
        assert len(content.faults) == len(karst_fault_off_bytes)

    def test_surface_resolution_positive(
        self,
        karst_nsim_data_dict,
        karst_dem_bytes,
        karst_voxels_str,
        karst_fault_off_bytes,
    ):
        from geocruncher.computations import KarstNSimData
        from geocruncher.karst.input import build_karst_content

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        content = build_karst_content(
            data, karst_dem_bytes, karst_voxels_str, karst_fault_off_bytes
        )
        assert content.surface_resolution.x > 0
        assert content.surface_resolution.y > 0


# ===========================================================================
# Coordinate tests - ensure all x/y coordinates are in local box coordinates, not absolute coordinates
# ===========================================================================


class TestCoordinates:
    def test_springs_within_project_box(self, karst_nsim_data_dict):
        from geocruncher.computations import KarstNSimData

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        box = data.project_box
        for s in data.springs:
            assert 0 <= s.x <= box.width, (
                f"Spring {s.poi_id} x={s.x:.1f} outside [0, {box.width:.1f}] — offset missing?"
            )
            assert 0 <= s.y <= box.height, (
                f"Spring {s.poi_id} y={s.y:.1f} outside [0, {box.height:.1f}] — offset missing?"
            )

    def test_catchments_within_project_box(self, karst_nsim_data_dict):
        from geocruncher.computations import KarstNSimData

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
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
        self, karst_nsim_data_dict, karst_fault_off_bytes
    ):
        """Fault vertex x/y must be in local box coordinates."""
        from geocruncher.computations import KarstNSimData
        from geocruncher.karst.input import load_fault_from_off

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        box = data.project_box
        eps = 0.1  # float32 rounding tolerance
        for fault_id, off_bytes in karst_fault_off_bytes.items():
            fault = load_fault_from_off(off_bytes)
            xs, ys = fault.vertices[:, 0], fault.vertices[:, 1]
            assert xs.min() >= -eps and xs.max() <= box.width + eps, (
                f"Fault {fault_id} x [{xs.min():.3f}, {xs.max():.3f}] outside [0, {box.width:.1f}]"
            )
            assert ys.min() >= -eps and ys.max() <= box.height + eps, (
                f"Fault {fault_id} y [{ys.min():.3f}, {ys.max():.3f}] outside [0, {box.height:.1f}]"
            )

    def test_springs_match_gwbs(self, karst_nsim_data_dict):
        """Every gwb.spring_id must have a matching spring."""
        from geocruncher.computations import KarstNSimData

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        spring_ids = {s.poi_id for s in data.springs}
        gwb_spring_ids = {g.spring_id for g in data.gwbs}
        missing = gwb_spring_ids - spring_ids
        assert not missing, (
            f"gwbs reference spring_id(s) {missing} with no matching spring — Spring backend sending incomplete data"
        )
