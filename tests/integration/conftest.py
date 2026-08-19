import json
import os
from pathlib import Path

import numpy as np
import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class FixtureProject:
    """A fixture project stored as a directory."""

    def __init__(self, root: Path):
        self.root = root

    def path(self, name: str) -> Path:
        return self.root / name

    def bytes(self, name: str) -> bytes:
        return self.path(name).read_bytes()

    def text(self, name: str) -> str:
        return self.path(name).read_text()

    def json(self, name: str):
        return json.loads(self.text(name))

    def glob(self, pattern: str):
        return sorted(self.root.glob(pattern))

    def names(self):
        return [
            path.relative_to(self.root).as_posix()
            for path in self.glob("**/*")
            if path.is_file()
        ]

    def json_matching(self, pattern: str):
        return [json.loads(path.read_text()) for path in self.glob(pattern)]

    def numbered_files(self, pattern: str, loader):
        return {
            int(path.stem.split("_")[-1]): loader(path) for path in self.glob(pattern)
        }

    def numbered_ids(self, pattern: str):
        return [int(path.stem.split("_")[-1]) for path in self.glob(pattern)]


class DummyProject(FixtureProject):
    """Direct computation inputs."""

    @property
    def xml(self) -> bytes:
        return self.bytes("geocruncher_project.xml")

    @property
    def dem(self) -> str:
        return self.text("geocruncher_dem.asc")


class GeneratedNetworkProject(FixtureProject):
    @property
    def dem_bytes(self) -> bytes:
        return self.bytes("dem_values.bin")

    @property
    def voxels_str(self) -> str:
        return self.text("voxels.txt")

    @property
    def fault_bytes(self) -> dict[int, bytes]:
        result = self.numbered_files("fault_*.bin", Path.read_bytes)
        assert result, "No fault_*.bin files found"
        return result

    @property
    def data_dict(self) -> dict:
        return {
            "simulation_params": self.json("config.json"),
            "project_box": self.json("project_box.json"),
            "dem_resolution": self.json("dem_resolution.json"),
            "stratigraphy": self.json("stratigraphy.json"),
            "voxels_units": self.json("voxels_units.json"),
            "fault_ids": self.numbered_ids("fault_*.bin"),
            "springs": self.json_matching("poi_*.json"),
            "gwbs": self.json_matching("gwb_*.json"),
            "is_base": False,
        }


@pytest.fixture(scope="session")
def generated_network_project():
    return GeneratedNetworkProject(
        Path(
            os.environ.get(
                "GENERATED_NETWORK_DATA_DIR",
                FIXTURES / "control_project",
            )
        )
    )


@pytest.fixture(scope="session")
def control_output():
    return (FIXTURES / "control_output.json").read_text()


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
def dummy_project():
    return DummyProject(FIXTURES / "dummy_project")


@pytest.fixture
def fixture_json(dummy_project):
    return dummy_project.json


@pytest.fixture
def fixture_bytes(dummy_project):
    return dummy_project.bytes


@pytest.fixture
def fixture_text(dummy_project):
    return dummy_project.text


@pytest.fixture
def decode_meshes(mesh_io):
    def decode(meshes):
        summaries = {}

        for name, data in meshes.items():
            assert isinstance(data, bytes)

            polydata = mesh_io.triangle_mesh_to_polydata(mesh_io.read_mesh(data))

            assert polydata.n_points > 0
            assert polydata.n_cells > 0
            assert np.isfinite(polydata.bounds).all()

            summaries[name] = (
                polydata.n_points,
                polydata.n_cells,
            )

        return summaries

    return decode
