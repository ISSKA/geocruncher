import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest


@dataclass(frozen=True)
class DummyProject:
    """Direct computation inputs: XML bytes and decoded DEM text.

    API smoke tests use ``fixture_bytes`` for multipart uploads; the API task
    layer decodes DEM bytes before calling the computation functions.
    """

    xml: bytes
    dem: str


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
