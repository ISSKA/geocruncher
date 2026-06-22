import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.native,
]

######## Fixtures/Fakes ########


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "dummy_project"
EXPECTED_TINY_UNIT_IDS = {"1", "2", "3", "4", "6", "8", "9"}
EXPECTED_MODEL_RANKS = {0.0, *map(float, range(1, 10))}


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
    return SimpleNamespace(
        xml=FIXTURE_DIR.joinpath("geocruncher_project.xml").read_bytes(),
        dem=FIXTURE_DIR.joinpath("geocruncher_dem.asc").read_text(),
    )


def _decode_meshes(mesh_io, meshes):
    summaries = {}
    for name, data in meshes.items():
        assert isinstance(data, bytes)
        polydata = mesh_io.read_mesh_to_polydata(data)
        assert polydata.n_points > 0
        assert polydata.n_cells > 0
        assert np.isfinite(polydata.bounds).all()
        summaries[name] = (polydata.n_points, polydata.n_cells)
    return summaries


def _fixture_json(name):
    return json.loads(FIXTURE_DIR.joinpath(name).read_text())


def _expected_slice_resolution(computations, data):
    box = next(iter(data["toCompute"].values()))[0]
    x_extent = round(box["xmax"]) - round(box["xmin"])
    y_extent = round(box["ymax"]) - round(box["ymin"])
    height = round(box["zmax"]) - round(box["zmin"])
    width = math.sqrt(x_extent**2 + y_extent**2)
    return computations.calculate_resolution(width, height, data["resolution"])


######## Tests ########


def test_real_compute_meshes_generates_decodable_tiny_dummy_project_meshes(
    computations, mesh_io, dummy_project
):
    result = computations.compute_meshes(
        _fixture_json("tiny_meshes.json"), dummy_project.xml, dummy_project.dem
    )

    assert set(result) == {"mesh", "fault"}
    assert set(result["mesh"]) == EXPECTED_TINY_UNIT_IDS
    assert set(result["fault"]) == {"topography"}

    unit_summaries = _decode_meshes(mesh_io, result["mesh"])
    fault_summaries = _decode_meshes(mesh_io, result["fault"])

    assert unit_summaries["1"] == (86, 168)
    assert fault_summaries["topography"] == (521, 952)


def test_real_compute_faults_generates_decodable_tiny_dummy_project_surface(
    computations, mesh_io, dummy_project
):
    result = computations.compute_faults(
        _fixture_json("tiny_meshes.json"), dummy_project.xml, dummy_project.dem
    )

    assert result["mesh"] == {}
    assert set(result["fault"]) == {"topography"}
    assert _decode_meshes(mesh_io, result["fault"]) == {"topography": (521, 952)}


def test_real_compute_intersections_generates_fixture_slice(
    computations, dummy_project
):
    data = _fixture_json("slice.json")
    section_id = next(iter(data["toCompute"]))
    expected_width, expected_height = _expected_slice_resolution(computations, data)

    result = computations.compute_intersections(
        data, dummy_project.xml, dummy_project.dem, {}
    )

    assert set(result) == {"mesh", "fault"}
    assert "forMaps" not in result["mesh"]
    assert result["fault"]["forMaps"] == {}
    assert result["mesh"]["drillholes"] == {section_id: []}
    assert result["mesh"]["springs"] == {section_id: []}
    assert result["mesh"]["matrixGwb"] == {section_id: []}
    assert result["fault"]["forCrossSections"] == {section_id: [{}]}

    section = result["mesh"]["forCrossSections"][section_id][0]
    assert len(section) == expected_width
    assert {len(row) for row in section} == {expected_height}
    assert {value for row in section for value in row} <= EXPECTED_MODEL_RANKS


def test_real_compute_tunnel_meshes_generates_decodable_tiny_meshes(
    computations, mesh_io
):
    result = computations.compute_tunnel_meshes(_fixture_json("tunnel.json"))

    assert set(result) == {"circle_tunnel", "rectangle_tunnel", "elliptic_tunnel"}
    assert _decode_meshes(mesh_io, result) == {
        "circle_tunnel": (48, 72),
        "rectangle_tunnel": (48, 72),
        "elliptic_tunnel": (48, 72),
    }
