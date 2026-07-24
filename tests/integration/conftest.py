import json
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

KARSTNSIM_DATA_ZIP = Path(
    os.environ.get(
        "KARSTNSIM_DATA_ZIP",
        Path(__file__).resolve().parents[1] / "fixtures" / "control_project.zip",
    )
)


@dataclass(frozen=True)
class DummyProject:
    """Direct computation inputs: XML bytes and decoded DEM text.

    API smoke tests use ``fixture_bytes`` for multipart uploads; the API task
    layer decodes DEM bytes before calling the computation functions.
    """

    xml: bytes
    dem: str


@dataclass(frozen=True)
class ZipFixture:
    archive: zipfile.ZipFile

    def bytes(self, name: str) -> bytes:
        return self.archive.read(name)

    def text(self, name: str) -> str:
        return self.bytes(name).decode("utf-8")

    def json(self, name: str):
        return json.loads(self.text(name))

    def names(self):
        return self.archive.namelist()


@pytest.fixture(scope="session")
def karstnsim_zip():
    with zipfile.ZipFile(KARSTNSIM_DATA_ZIP, "r") as zf:
        yield ZipFixture(zf)


@pytest.fixture(scope="session")
def karstnsim_dem_bytes(karstnsim_zip):
    return karstnsim_zip.bytes("dem_values.bin")


@pytest.fixture(scope="session")
def karstnsim_voxels_str(karstnsim_zip):
    return karstnsim_zip.text("voxels.txt")


@pytest.fixture(scope="session")
def karstnsim_fault_bytes(karstnsim_zip) -> dict[int, bytes]:
    """Dict of fault_id -> OFF bytes."""
    result = {}

    for name in sorted(karstnsim_zip.names()):
        if name.startswith("fault_") and name.endswith(".bin"):
            fault_id = int(Path(name).stem.split("_")[1])
            result[fault_id] = karstnsim_zip.bytes(name)

    assert result, "No fault_*.bin files found in zip"
    return result


@pytest.fixture(scope="session")
def karstnsim_data_dict(karstnsim_zip) -> dict:
    """The JSON body that Spring would POST to /compute/karstnsim."""

    config = karstnsim_zip.json("config.json")
    project_box = karstnsim_zip.json("project_box.json")
    dem_res = karstnsim_zip.json("dem_resolution.json")
    stratigraphy = karstnsim_zip.json("stratigraphy.json")
    vox_units = karstnsim_zip.json("voxels_units.json")

    gwbs = [
        karstnsim_zip.json(name)
        for name in sorted(karstnsim_zip.names())
        if name.startswith("gwb_") and name.endswith(".json")
    ]

    springs = [
        karstnsim_zip.json(name)
        for name in sorted(karstnsim_zip.names())
        if name.startswith("poi_") and name.endswith(".json")
    ]

    fault_ids = [
        int(Path(name).stem.split("_")[1])
        for name in sorted(karstnsim_zip.names())
        if name.startswith("fault_") and name.endswith(".bin")
    ]

    return {
        "simulation_params": config,
        "project_box": project_box,
        "dem_resolution": dem_res,
        "stratigraphy": stratigraphy,
        "voxels_units": vox_units,
        "fault_ids": fault_ids,
        "springs": springs,
        "gwbs": gwbs,
    }


@pytest.fixture(scope="session")
def control_output():
    return (
        Path(__file__).parent.parent / "fixtures" / "control_output.json"
    ).read_text()


@pytest.fixture(scope="module")
def computations():
    pytest.importorskip("DracoPy")
    pytest.importorskip("PyGeoAlgo")
    pytest.importorskip("forgeo")
    pytest.importorskip("pyvista")
    return pytest.importorskip("geocruncher.computations")


@pytest.fixture(scope="module")
def mesh_io():
    return pytest.importorskip("geocruncher.mesh_io.mesh_io")


@pytest.fixture(scope="module")
def dummy_project_dir():
    return Path(__file__).resolve().parents[1] / "fixtures" / "dummy_project"


@pytest.fixture(scope="module")
def dummy_project(dummy_project_dir):
    return DummyProject(
        xml=dummy_project_dir.joinpath("geocruncher_project.xml").read_bytes(),
        dem=dummy_project_dir.joinpath("geocruncher_dem.asc").read_text(),
    )


@pytest.fixture
def fixture_json(dummy_project_dir):
    def load(name):
        return json.loads(dummy_project_dir.joinpath(name).read_text())

    return load


@pytest.fixture
def fixture_bytes(dummy_project_dir):
    def load(name):
        return dummy_project_dir.joinpath(name).read_bytes()

    return load


@pytest.fixture
def fixture_text(dummy_project_dir):
    def load(name):
        return dummy_project_dir.joinpath(name).read_text()

    return load


@pytest.fixture
def decode_meshes(mesh_io):
    def decode(meshes):
        summaries = {}
        for name, data in meshes.items():
            assert isinstance(data, bytes)
            polydata = mesh_io.read_mesh_to_polydata(data)
            assert polydata.n_points > 0
            assert polydata.n_cells > 0
            assert np.isfinite(polydata.bounds).all()
            summaries[name] = (polydata.n_points, polydata.n_cells)
        return summaries

    return decode
