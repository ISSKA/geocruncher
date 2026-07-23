import numpy as np
import pytest

from geocruncher.karstnsim.input import build_karstnsim_content
from tests.fixtures.payloads import (
    KARSTNSIM_DATA,
    KARSTNSIM_DEM_BYTES,
    KARSTNSIM_FAULT_BYTES,
    KARSTNSIM_VOXELS_STR,
)


@pytest.fixture
def synthetic_karstnsim_content(
    karstnsim_data_adapter,
):
    from geocruncher.karstnsim.input import build_karstnsim_content

    data = karstnsim_data_adapter.validate_python(KARSTNSIM_DATA)

    return build_karstnsim_content(
        data,
        KARSTNSIM_DEM_BYTES,
        KARSTNSIM_VOXELS_STR,
        KARSTNSIM_FAULT_BYTES,
    )


class TestLoadVoxels:
    def test_parses_header_and_voxels(self):
        from geocruncher.karstnsim.input import load_voxels

        voxels_lines = KARSTNSIM_VOXELS_STR.splitlines()

        voxels = load_voxels(list(voxels_lines))

        assert voxels.shape == (2, 2, 1, 2)
        assert voxels.dtype == np.int32

        assert voxels[0, 0, 0].tolist() == [1, 10]
        assert voxels[1, 0, 0].tolist() == [2, 20]
        assert voxels[0, 1, 0].tolist() == [3, 30]
        assert voxels[1, 1, 0].tolist() == [4, 40]

    def test_preserves_xyz_order_for_3d_grid(self):
        from geocruncher.karstnsim.input import load_voxels

        voxels_lines = [
            "XMIN=0 XMAX=2 YMIN=0 YMAX=2 ZMIN=0 ZMAX=2 NUMBERX=2 NUMBERY=2 NUMBERZ=2 NOVALUE=0",
            "rank gwb_id",
            "1 101",
            "2 102",
            "3 103",
            "4 104",
            "5 105",
            "6 106",
            "7 107",
            "8 108",
        ]

        voxels = load_voxels(voxels_lines)

        assert voxels.shape == (2, 2, 2, 2)

        assert voxels[0, 0, 0, 0] == 1
        assert voxels[1, 0, 0, 0] == 2
        assert voxels[0, 1, 0, 0] == 3
        assert voxels[1, 1, 0, 0] == 4
        assert voxels[0, 0, 1, 0] == 5
        assert voxels[1, 1, 1, 0] == 8

    def test_accepts_single_voxel_grid(self):
        from geocruncher.karstnsim.input import load_voxels

        voxels_lines = [
            "XMIN=0 XMAX=1 YMIN=0 YMAX=1 ZMIN=0 ZMAX=1 NUMBERX=1 NUMBERY=1 NUMBERZ=1 NOVALUE=0",
            "rank gwb_id",
            "99 123",
        ]

        voxels = load_voxels(voxels_lines)

        assert voxels.shape == (1, 1, 1, 2)
        assert voxels[0, 0, 0].tolist() == [99, 123]

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

    def test_rejects_invalid_voxel_table_shape(self):
        from geocruncher.karstnsim.input import load_voxels

        voxels_lines = [
            "XMIN=0 XMAX=1 YMIN=0 YMAX=1 ZMIN=0 ZMAX=1 NUMBERX=1 NUMBERY=1 NUMBERZ=1 NOVALUE=0",
            "rank gwb_id",
            "10",
        ]

        with pytest.raises(ValueError):
            load_voxels(voxels_lines)


class TestBuildKarstNSimContent:
    def test_transforms_surface(
        self,
        synthetic_karstnsim_content,
    ):
        expected_surface = np.array(
            # resampled + flipped version of 4x4 [[1, 2, 3, 4], .... , [13, 14, 15, 16]]
            [
                [9, 11],
                [1, 3],
            ],
            dtype=np.float32,
        )

        np.testing.assert_array_equal(
            synthetic_karstnsim_content.surface_data,
            expected_surface,
        )

    def test_rejects_single_cell_dem(
        self,
        karstnsim_data_adapter,
    ):
        data = karstnsim_data_adapter.validate_python(
            {
                **KARSTNSIM_DATA,
                "dem_resolution": {
                    "x": 1,
                    "y": 1,
                },
            }
        )

        with pytest.raises(
            ValueError,
            match="Surface data grid must have at least 2 rows",
        ):
            build_karstnsim_content(
                data,
                np.array([[1]], dtype=np.float32).tobytes(),
                KARSTNSIM_VOXELS_STR,
                {},
            )

    def test_loads_all_faults(self, monkeypatch, karstnsim_data_adapter):
        calls = []

        def fake_load_fault(data):
            calls.append(data)
            return "mesh"

        monkeypatch.setattr(
            "geocruncher.karstnsim.input.load_fault",
            fake_load_fault,
        )

        content = build_karstnsim_content(
            karstnsim_data_adapter.validate_python(KARSTNSIM_DATA),
            KARSTNSIM_DEM_BYTES,
            KARSTNSIM_VOXELS_STR,
            {1: b"a", 2: b"b"},
        )

        assert content.faults == ["mesh", "mesh"]
        assert calls == [b"a", b"b"]
