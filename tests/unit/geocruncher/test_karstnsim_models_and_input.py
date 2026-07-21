import numpy as np
import pytest

from geocruncher.mesh_io.triangle_mesh import TriangleMesh


@pytest.fixture(scope="session")
def karstnsim_content(
    karstnsim_data_dict,
    karstnsim_dem_bytes,
    karstnsim_voxels_str,
    karstnsim_fault_bytes,
    karstnsim_data_adapter,
):
    from geocruncher.karstnsim.input import build_karstnsim_content

    data = karstnsim_data_adapter.validate_python(karstnsim_data_dict)

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


######## Model Tests ########


class TestSimulationParameters:
    def test_camel_case_aliases(self):
        from geocruncher.karstnsim.models import SimulationParameters

        params = SimulationParameters.model_validate(
            {
                "kPts": 15,
                "cohesionFactor": 0.8,
                "nSinks": 200,
                "seed": 99,
            }
        )

        assert params.k_pts == 15
        assert params.cohesion_factor == 0.8
        assert params.n_sinks == 200
        assert params.seed == 99


class TestKarstNSimProjectBox:
    def test_depth_property(self):
        from geocruncher.karstnsim.models import KarstNSimProjectBox

        box = KarstNSimProjectBox.model_validate(
            {
                "width": 1000.0,
                "height": 500.0,
                "min_elevation": 120.0,
                "max_elevation": 320.0,
            }
        )
        assert box.depth == pytest.approx(200.0)


class TestKarstNSimGeologicalUnit:
    def test_rejects_invalid_permeability(self):
        from pydantic import ValidationError

        from geocruncher.karstnsim.models import KarstNSimGeologicalUnit

        with pytest.raises(ValidationError):
            KarstNSimGeologicalUnit.model_validate(
                {
                    "name": "Aquifer",
                    "permeability": "NotARealValue",
                    "stratiUnitId": 7,
                }
            )


######## Input parsing tests ########


class TestLoadVoxels:
    def test_parses_header_and_voxels(self):
        from geocruncher.karstnsim.input import load_voxels

        voxels_lines = [
            "XMIN=0 XMAX=2 YMIN=0 YMAX=1 ZMIN=0 ZMAX=2 NUMBERX=2 NUMBERY=1 NUMBERZ=2 NOVALUE=0",
            "rank gwb_id",
            "10 100",
            "20 200",
            "30 300",
            "40 400",
        ]

        header, voxels = load_voxels(voxels_lines)

        assert (header.nx, header.ny, header.nz) == (2, 1, 2)
        assert header.novalue == 0
        assert voxels.shape == (2, 1, 2, 2)
        assert voxels.dtype == np.int32
        assert voxels[0, 0, 0].tolist() == [10, 100]
        assert voxels[1, 0, 0].tolist() == [20, 200]
        assert voxels[0, 0, 1].tolist() == [30, 300]
        assert voxels[1, 0, 1].tolist() == [40, 400]

    def test_rejects_malformed_header_line(self):
        from geocruncher.karstnsim.input import load_voxels

        voxels_lines = [
            "XMIN=0 XMAX=2 YMIN=0 YMAX=1 ZMIN=0 ZMAX=2 NUMBERX=2 NUMBERY=1 NUMBERZ=2",
            "rank gwb_id",
            "10 100",
            "20 200",
        ]

        with pytest.raises(ValueError, match="Malformed voxel header line"):
            load_voxels(voxels_lines)

    def test_rejects_short_file(self):
        from geocruncher.karstnsim.input import load_voxels

        with pytest.raises(ValueError, match="at least 3 lines"):
            load_voxels(["header", "rank gwb_id"])

    def test_rejects_voxel_count_mismatch(self):
        from geocruncher.karstnsim.input import load_voxels

        voxels_lines = [
            "XMIN=0 XMAX=2 YMIN=0 YMAX=1 ZMIN=0 ZMAX=2 NUMBERX=2 NUMBERY=1 NUMBERZ=2 NOVALUE=0",
            "rank gwb_id",
            "10 100",
            "20 200",
            "30 300",
        ]

        with pytest.raises(ValueError, match="Voxel count mismatch"):
            load_voxels(voxels_lines)


class TestLoadFault:
    def test_load_fault_delegates_to_read_mesh(self, monkeypatch):
        from geocruncher.karstnsim import input as karst_input

        expected = TriangleMesh(
            vertices=np.array([[1.0, 2.0, 3.0]], dtype=np.float64),
            triangles=np.array([[0, 0, 0]], dtype=np.int32),
        )
        captured = {}

        def fake_read_mesh(data):
            captured["data"] = data
            return expected

        monkeypatch.setattr(karst_input, "read_mesh", fake_read_mesh)

        result = karst_input.load_fault(b"fault-bytes")

        assert result is expected
        assert captured["data"] == b"fault-bytes"


class TestBuildKarstNSimContent:
    def test_transforms_surface_and_resolutions(
        self,
        karstnsim_content,
        karstnsim_data_dict,
        karstnsim_dem_bytes,
        parsed_voxels,
    ):
        header, _ = parsed_voxels
        dem_resolution = karstnsim_data_dict["dem_resolution"]
        raw_surface = np.frombuffer(karstnsim_dem_bytes, dtype=np.float32).reshape(
            dem_resolution["y"],
            dem_resolution["x"],
        )
        expected_surface = raw_surface[
            :: dem_resolution["y"] // karstnsim_content.compute_resolution["y"],
            :: dem_resolution["x"] // karstnsim_content.compute_resolution["x"],
        ]
        expected_surface = np.flipud(expected_surface).copy()

        np.testing.assert_allclose(karstnsim_content.surface_data, expected_surface)
        assert karstnsim_content.surface_data.shape == (
            karstnsim_content.resampled_dem_resolution["y"],
            karstnsim_content.resampled_dem_resolution["x"],
        )
        assert karstnsim_content.compute_resolution["x"] == header.nx
        assert karstnsim_content.compute_resolution["y"] == header.ny
        assert karstnsim_content.compute_resolution["z"] == header.nz
