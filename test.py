"""
Tests for geocruncher/karst/ integration.

Run with:
    pytest test_karst.py -v

Grouped into 3 layers:
  - Layer 1: models.py         (no pykarstnsim needed)
  - Layer 2: input.py          (no pykarstnsim needed)
  - Layer 3: simulation.py     (requires pykarstnsim, run separately)

Set TEST_DATA_DIR to the directory containing the extracted zip files:
    export TEST_DATA_DIR=/path/to/export_inspect
"""

import json
import os
import struct
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Fixtures — real data from the export zip
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.environ.get("TEST_DATA_DIR", "./export_inspect"))


def _read(filename: str) -> bytes:
    return (DATA_DIR / filename).read_bytes()


def _read_text(filename: str) -> str:
    return (DATA_DIR / filename).read_text(encoding="utf-8")


def _fault_bin_to_off(bin_bytes: bytes) -> bytes:
    """Convert the Angular custom binary fault format to OFF, to simulate
    what Spring will send to the API once the export service is removed."""
    offset = 0
    n_verts = struct.unpack_from("<i", bin_bytes, offset)[0]
    offset += 4
    verts = []
    for _ in range(n_verts):
        x, y, z = struct.unpack_from("<fff", bin_bytes, offset)
        offset += 12
        verts.append((x, y, z))
    n_tris = struct.unpack_from("<i", bin_bytes, offset)[0]
    offset += 4
    tris = []
    for _ in range(n_tris):
        a, b, c = struct.unpack_from("<iii", bin_bytes, offset)
        offset += 12
        tris.append((a, b, c))
    lines = ["OFF", f"{n_verts} {n_tris} 0"]
    for v in verts:
        lines.append(f"{v[0]} {v[1]} {v[2]}")
    for t in tris:
        lines.append(f"3 {t[0]} {t[1]} {t[2]}")
    return "\n".join(lines).encode("utf-8")


@pytest.fixture(scope="session")
def dem_bytes():
    return _read("dem_values.bin")


@pytest.fixture(scope="session")
def voxels_str():
    return _read_text("voxels.txt")


@pytest.fixture(scope="session")
def fault_off_bytes():
    """Dict of fault_id → OFF bytes, converted from the zip .bin files."""
    return {
        418: _fault_bin_to_off(_read("fault_418.bin")),
        419: _fault_bin_to_off(_read("fault_419.bin")),
        420: _fault_bin_to_off(_read("fault_420.bin")),
        421: _fault_bin_to_off(_read("fault_421.bin")),
    }


@pytest.fixture(scope="session")
def karst_nsim_data_dict():
    """The JSON body that Spring would POST to /compute/karstnsim."""
    config = json.loads(_read_text("config.json"))
    project_box = json.loads(_read_text("project_box.json"))
    dem_res = json.loads(_read_text("dem_resolution.json"))
    stratigraphy = json.loads(_read_text("stratigraphy.json"))
    vox_units = json.loads(_read_text("voxels_units.json"))
    vox_header = _read_text("voxels.txt").splitlines()[0]

    # Parse voxels header into a dict
    parts = dict(p.split("=") for p in vox_header.split())
    voxels_header = {
        "xmin": float(parts["XMIN"]),
        "xmax": float(parts["XMAX"]),
        "ymin": float(parts["YMIN"]),
        "ymax": float(parts["YMAX"]),
        "zmin": float(parts["ZMIN"]),
        "zmax": float(parts["ZMAX"]),
        "nx": int(parts["NUMBERX"]),
        "ny": int(parts["NUMBERY"]),
        "nz": int(parts["NUMBERZ"]),
        "novalue": int(parts["NOVALUE"]),
    }

    gwbs = [
        json.loads(_read_text("gwb_96.json")),
        json.loads(_read_text("gwb_97.json")),
    ]
    springs = [json.loads(_read_text("poi_5_spring_2.json"))]
    springs = [json.loads(_read_text("poi_6_spring_3.json"))]

    return {
        "simulation_params": config,
        "project_box": project_box,
        "dem_resolution": dem_res,
        "stratigraphy": stratigraphy,
        "voxels_header": voxels_header,
        "voxels_units": vox_units,
        "fault_ids": [418, 419, 420, 421],
        "springs": springs,
        "gwbs": gwbs,
    }


# ===========================================================================
# Layer 1 — models.py
# No pykarstnsim dependency. These should always pass.
# ===========================================================================


class TestModels:
    def test_simulation_parameters_camel_case(self, karst_nsim_data_dict):
        """SimulationParameters must accept camelCase keys from config.json."""
        from geocruncher.karst.models import SimulationParameters

        params = SimulationParameters.model_validate(
            karst_nsim_data_dict["simulation_params"]
        )
        assert params.seed == 42
        assert params.k_pts == 20
        assert params.cohesion_factor == 0.993
        assert params.n_sinks == 658

    def test_karst_project_box(self, karst_nsim_data_dict):
        from geocruncher.karst.models import KarstProjectBox

        box = KarstProjectBox.model_validate(karst_nsim_data_dict["project_box"])
        assert box.width == pytest.approx(14999.7, rel=1e-3)
        assert box.height == pytest.approx(9999.7, rel=1e-3)
        assert box.depth == pytest.approx(7500.0, rel=1e-3)

    def test_karst_dem_resolution(self, karst_nsim_data_dict):
        from geocruncher.karst.models import KarstDemResolution

        res = KarstDemResolution.model_validate(karst_nsim_data_dict["dem_resolution"])
        assert res.n_cols == 601
        assert res.n_rows == 401

    def test_geological_unit_extra_fields_ignored(self, karst_nsim_data_dict):
        """stratigraphy.json has extra fields (opacity, colour, id) that must be ignored."""
        from geocruncher.karst.models import KarstGeologicalUnit

        raw = karst_nsim_data_dict["stratigraphy"][0]
        assert "opacity" in raw
        unit = KarstGeologicalUnit.model_validate(raw)
        assert unit.name == "Molasse"
        assert unit.permeability.value == "Karstified"
        assert unit.strati_unit_id == 7

    def test_karst_spring(self, karst_nsim_data_dict):
        from geocruncher.karst.models import KarstSpring

        raw = karst_nsim_data_dict["springs"][0]
        spring = KarstSpring.model_validate(raw)
        assert spring.poi_id == 6
        assert len(spring.catchment) == 6

    def test_karst_nsim_data_full(self, karst_nsim_data_dict):
        """Full KarstNSimData round-trip from the dict Spring would POST."""
        from geocruncher.computations import KarstNSimData

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        assert len(data.stratigraphy) == 7
        assert len(data.gwbs) == 2
        assert len(data.fault_ids) == 4
        assert data.voxels_units == [12, 11, 10, 9, 8, 7]


# ===========================================================================
# Layer 2 — input.py
# No pykarstnsim dependency. Tests parsing and build_karst_content.
# ===========================================================================


class TestInput:
    def test_load_voxels_header(self, voxels_str):
        from geocruncher.karst.input import load_voxels

        header, voxels = load_voxels(voxels_str.splitlines())
        assert header.nx == 150
        assert header.ny == 100
        assert header.nz == 75
        assert voxels.shape == (150, 100, 75, 2)
        assert voxels.dtype == np.int32

    def test_load_voxels_count(self, voxels_str):
        from geocruncher.karst.input import load_voxels

        header, voxels = load_voxels(voxels_str.splitlines())
        # total cells must match header
        assert voxels.shape == (header.nx, header.ny, header.nz, 2)

    def test_load_fault_from_off_shape(self, fault_off_bytes):
        from geocruncher.karst.input import load_fault_from_off

        fault = load_fault_from_off(fault_off_bytes[418])
        assert fault.vertices.shape == (23692, 3)
        assert fault.triangles.shape == (45938, 3)
        assert fault.vertices.dtype == np.float32
        assert fault.triangles.dtype == np.int32

    def test_load_fault_from_off_all_faults(self, fault_off_bytes):
        from geocruncher.karst.input import load_fault_from_off

        for fault_id, off_bytes in fault_off_bytes.items():
            fault = load_fault_from_off(off_bytes)
            assert fault.vertices.ndim == 2 and fault.vertices.shape[1] == 3
            assert fault.triangles.ndim == 2 and fault.triangles.shape[1] == 3

    def test_build_karst_content_surface_data_shape(
        self, karst_nsim_data_dict, dem_bytes, voxels_str, fault_off_bytes
    ):
        from geocruncher.computations import KarstNSimData
        from geocruncher.karst.input import build_karst_content

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        content = build_karst_content(data, dem_bytes, voxels_str, fault_off_bytes)
        # surface_data must have at least 2 rows and 2 cols after resampling
        assert content.surface_data.ndim == 2
        assert content.surface_data.shape[0] >= 2
        assert content.surface_data.shape[1] >= 2

    def test_build_karst_content_compute_resolution(
        self, karst_nsim_data_dict, dem_bytes, voxels_str, fault_off_bytes
    ):
        from geocruncher.computations import KarstNSimData
        from geocruncher.karst.input import build_karst_content

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        content = build_karst_content(data, dem_bytes, voxels_str, fault_off_bytes)
        # compute resolution must match voxels header
        assert content.compute_resolution["x"] == 150
        assert content.compute_resolution["y"] == 100
        assert content.compute_resolution["z"] == 75

    def test_build_karst_content_faults(
        self, karst_nsim_data_dict, dem_bytes, voxels_str, fault_off_bytes
    ):
        from geocruncher.computations import KarstNSimData
        from geocruncher.karst.input import build_karst_content

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        content = build_karst_content(data, dem_bytes, voxels_str, fault_off_bytes)
        assert len(content.faults) == 4

    def test_build_karst_content_surface_resolution(
        self, karst_nsim_data_dict, dem_bytes, voxels_str, fault_off_bytes
    ):
        from geocruncher.computations import KarstNSimData
        from geocruncher.karst.input import build_karst_content

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        content = build_karst_content(data, dem_bytes, voxels_str, fault_off_bytes)
        # surface_resolution must be positive
        assert content.surface_resolution.x > 0
        assert content.surface_resolution.y > 0

    def test_build_karst_content_dem_values_reasonable(
        self, karst_nsim_data_dict, dem_bytes, voxels_str, fault_off_bytes
    ):
        from geocruncher.computations import KarstNSimData
        from geocruncher.karst.input import build_karst_content

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        content = build_karst_content(data, dem_bytes, voxels_str, fault_off_bytes)
        # elevation values should be in a plausible range for this project
        assert content.surface_data.min() > -500
        assert content.surface_data.max() < 3000


# ===========================================================================
# Layer 3 — simulation.py
# Requires pykarstnsim. Run only when the lib is installed.
# ===========================================================================


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("pykarstnsim"),
    reason="pykarstnsim not installed",
)
class TestSimulation:
    def test_run_karst_simulation_returns_bytes(
        self, karst_nsim_data_dict, dem_bytes, voxels_str, fault_off_bytes
    ):
        from geocruncher.computations import KarstNSimData
        from geocruncher.karst.simulation import run_karst_simulation

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        result = run_karst_simulation(data, dem_bytes, voxels_str, fault_off_bytes)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_run_karst_simulation_output_format(
        self, karst_nsim_data_dict, dem_bytes, voxels_str, fault_off_bytes
    ):
        from geocruncher.computations import KarstNSimData
        from geocruncher.karst.simulation import run_karst_simulation

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        result_bytes = run_karst_simulation(
            data, dem_bytes, voxels_str, fault_off_bytes
        )
        text = result_bytes.decode("utf-8")
        assert "# Run info" in text
        assert "# Data" in text
        # Run info block must be valid JSON
        info_block = text.split("# Run info\n")[1].split("\n# Data")[0]
        parsed = json.loads(info_block)
        assert "metadata" in parsed
        assert "config" in parsed
        assert parsed["metadata"]["computeResolution"]["x"] == 150

    def test_run_karst_simulation_invalid_spring_raises(
        self, karst_nsim_data_dict, dem_bytes, voxels_str, fault_off_bytes
    ):
        """A spring with no matching gwb should raise ValueError, not exit()."""
        from geocruncher.computations import KarstNSimData
        from geocruncher.karst.simulation import run_karst_simulation

        broken = dict(karst_nsim_data_dict)
        broken["gwbs"] = []  # remove all gwbs so no spring can resolve a water table
        data = KarstNSimData.model_validate(broken)
        with pytest.raises(ValueError, match="groundwater body"):
            run_karst_simulation(data, dem_bytes, voxels_str, fault_off_bytes)
