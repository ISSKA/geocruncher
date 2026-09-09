import math

import numpy as np
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.native,
]

EXPECTED_TINY_UNIT_UUIDS = {
    "32145afb-ed7f-5b5f-8667-8062d1642472",
    "3896929f-2f47-5877-b4a0-e187673a8c39",
    "96fb037a-c4e1-5755-b17d-d139f36cd21b",
    "a96e0c19-5b77-5aa7-b44a-2a787837c587",
    "b607bfee-f661-5266-874c-477d2222fa5f",
    "d41e20f0-b20f-5641-97f1-63d0b619007d",
    "dummyFormation",
}

EXPECTED_MODEL_UNIT_UUIDS = {
    "32145afb-ed7f-5b5f-8667-8062d1642472",
    "c8467ee4-fb7d-5038-8e48-d9b18493319b",
    "b607bfee-f661-5266-874c-477d2222fa5f",
    "dummyFormation",
    "8433dc05-22f6-531e-87c4-cfdb143c112b",
    "96fb037a-c4e1-5755-b17d-d139f36cd21b",
    "a96e0c19-5b77-5aa7-b44a-2a787837c587",
    "3896929f-2f47-5877-b4a0-e187673a8c39",
    "SKY",
    "d41e20f0-b20f-5641-97f1-63d0b619007d",
}

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
    assert set(result["mesh"]) == EXPECTED_TINY_UNIT_UUIDS
    assert set(result["fault"]) == {"topography"}

    unit_summaries = decode_meshes(result["mesh"])
    fault_summaries = decode_meshes(result["fault"])

    assert unit_summaries["32145afb-ed7f-5b5f-8667-8062d1642472"] == (26, 40)
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
    assert {value for row in section for value in row} <= EXPECTED_MODEL_UNIT_UUIDS


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
        EXPECTED_MODEL_UNIT_UUIDS
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

    result = computations.compute_gwb_meshes(
        {"1": unit_meshes["32145afb-ed7f-5b5f-8667-8062d1642472"]}, springs
    )

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
