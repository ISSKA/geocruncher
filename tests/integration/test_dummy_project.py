import math

import numpy as np
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.native,
]

EXPECTED_TINY_UNIT_IDS = {"1", "2", "3", "4", "6", "8", "9"}
EXPECTED_MODEL_RANKS = {0.0, *map(float, range(1, 10))}


def _expected_slice_resolution(computations, data):
    box = next(iter(data["toCompute"].values()))[0]
    x_extent = round(box["xmax"]) - round(box["xmin"])
    y_extent = round(box["ymax"]) - round(box["ymin"])
    height = round(box["zmax"]) - round(box["zmin"])
    width = math.sqrt(x_extent**2 + y_extent**2)
    return computations.calculate_resolution(width, height, data["resolution"])


######## Tests ########


def test_real_compute_meshes_generates_decodable_tiny_dummy_project_meshes(
    computations, decode_meshes, dummy_project, fixture_json, protobuf_model
):
    result = computations.compute_meshes(
        fixture_json("mesh.json"), protobuf_model, dummy_project.dem
    )

    assert set(result) == {"mesh", "fault"}
    assert set(result["mesh"]) == EXPECTED_TINY_UNIT_IDS
    assert set(result["fault"]) == {"topography"}

    unit_summaries = decode_meshes(result["mesh"])
    fault_summaries = decode_meshes(result["fault"])

    assert unit_summaries["1"] == (86, 168)
    assert fault_summaries["topography"] == (521, 952)


def test_real_compute_faults_generates_decodable_tiny_dummy_project_surface(
    computations, decode_meshes, dummy_project, fixture_json, protobuf_model
):
    result = computations.compute_faults(
        fixture_json("mesh.json"), protobuf_model, dummy_project.dem
    )

    assert result["mesh"] == {}
    assert set(result["fault"]) == {"topography"}
    assert decode_meshes(result["fault"]) == {"topography": (521, 952)}


def test_real_compute_intersections_generates_fixture_slice(
    computations, dummy_project, fixture_json, protobuf_model
):
    data = fixture_json("intersection.json")
    section_id = next(iter(data["toCompute"]))
    expected_width, expected_height = _expected_slice_resolution(computations, data)

    result = computations.compute_intersections(
        data, protobuf_model, dummy_project.dem, {}
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


def test_real_compute_voxels_generates_tiny_vox_grid(
    computations, dummy_project, fixture_json, protobuf_model
):
    result = computations.compute_voxels(
        fixture_json("mesh.json"), protobuf_model, dummy_project.dem, {}
    )

    lines = result.splitlines()
    assert "NUMBERX=5" in lines[0]
    assert "NUMBERY=5" in lines[0]
    assert "NUMBERZ=5" in lines[0]
    assert lines[1] == "rank gwb_id"

    rows = lines[2:]
    assert len(rows) == 125
    assert {int(row.split()[1]) for row in rows} == {0}
    for row in rows:
        rank, gwb_id = row.split()
        assert float(rank) in EXPECTED_MODEL_RANKS
        assert gwb_id == "0"


def test_real_compute_voxels_tags_gwb_mesh_points(
    computations, dummy_project, fixture_bytes, fixture_json, protobuf_model
):
    result = computations.compute_voxels(
        fixture_json("mesh.json"),
        protobuf_model,
        dummy_project.dem,
        {"7": [fixture_bytes("gwb_meshes/7.off")]},
    )

    lines = result.splitlines()
    assert lines[1] == "rank gwb_id"

    rows = lines[2:]
    assert len(rows) == 125
    assert {int(row.split()[1]) for row in rows} == {0, 7}
    for row in rows:
        rank, gwb_id = row.split()
        assert float(rank) in EXPECTED_MODEL_RANKS
        assert gwb_id in {"0", "7"}


def test_real_compute_intersections_generates_map_outputs(
    computations, dummy_project, fixture_json, protobuf_model
):
    data = fixture_json("intersection_map.json")
    section_id = next(iter(data["toCompute"]))
    expected_width, expected_height = _expected_slice_resolution(computations, data)

    result = computations.compute_intersections(
        data, protobuf_model, dummy_project.dem, {}
    )

    assert "forMaps" in result["mesh"]
    assert len(result["mesh"]["forMaps"]) == 25
    assert {len(row) for row in result["mesh"]["forMaps"]} == {17}
    assert {value for row in result["mesh"]["forMaps"] for value in row} <= (
        EXPECTED_MODEL_RANKS
    )
    assert "forMaps" in result["fault"]
    assert isinstance(result["fault"]["forMaps"], dict)

    section = result["mesh"]["forCrossSections"][section_id][0]
    assert len(section) == expected_width
    assert {len(row) for row in section} == {expected_height}


def test_real_compute_intersections_projects_hydro_features_and_gwb_matrix(
    computations, dummy_project, fixture_bytes, fixture_json, protobuf_model
):
    data = fixture_json("intersection_hydro.json")
    section_id = next(iter(data["toCompute"]))
    expected_width, expected_height = _expected_slice_resolution(computations, data)

    result = computations.compute_intersections(
        data,
        protobuf_model,
        dummy_project.dem,
        {"7": [fixture_bytes("gwb_meshes/7.off")]},
    )

    springs = result["mesh"]["springs"][section_id][0]
    drillholes = result["mesh"]["drillholes"][section_id][0]
    matrix_gwb = result["mesh"]["matrixGwb"][section_id][0]

    assert set(springs) == {"spring-1"}
    np.testing.assert_allclose(
        springs["spring-1"], [8184.030841075725, 500.0], atol=1e-3
    )
    assert set(drillholes) == {"drillhole-1"}
    np.testing.assert_allclose(
        drillholes["drillhole-1"],
        [[8184.030841075725, -1000.0], [8184.030841075725, 1250.0]],
        atol=1e-3,
    )
    assert len(matrix_gwb) == expected_width * expected_height
    assert set(matrix_gwb) == {0, 7}


def test_real_compute_gwb_meshes_returns_decodable_aquifer(
    computations, mesh_io, dummy_project, fixture_json, protobuf_model
):
    unit_meshes = computations.compute_meshes(
        fixture_json("mesh.json"), protobuf_model, dummy_project.dem
    )["mesh"]
    springs = fixture_json("gwb_spring.json")

    result = computations.compute_gwb_meshes({"1": unit_meshes["1"]}, springs)

    assert set(result) == {"metadata", "meshes"}
    assert len(result["metadata"]) == 1
    assert result["metadata"][0]["unit_id"] == 1
    assert result["metadata"][0]["spring_id"] == 1
    assert result["metadata"][0]["volume"] > 0
    assert len(result["meshes"]) == 1

    polydata = mesh_io.read_mesh_to_polydata(result["meshes"][0])
    assert polydata.n_points > 0
    assert polydata.n_cells > 0
    assert np.isfinite(polydata.bounds).all()
    assert polydata.bounds[5] <= springs[0]["location"]["z"] + 1.0


def test_real_compute_tunnel_meshes_generates_decodable_tiny_meshes(
    computations, decode_meshes, fixture_json
):
    result = computations.compute_tunnel_meshes(fixture_json("tunnel.json"))

    assert set(result) == {"circle_tunnel", "rectangle_tunnel", "elliptic_tunnel"}
    assert decode_meshes(result) == {
        "circle_tunnel": (48, 72),
        "rectangle_tunnel": (48, 72),
        "elliptic_tunnel": (48, 72),
    }
