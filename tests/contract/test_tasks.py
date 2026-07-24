import json

import pytest

import api.tasks as tasks
from geocruncher.karstnsim.models import KarstNSimData
from tests.fixtures.payloads import (
    INTERSECTIONS_DATA,
    KARSTNSIM_DATA,
    KARSTNSIM_DEM_BYTES,
    KARSTNSIM_FAULT_BYTES,
    KARSTNSIM_VOXELS_STR,
    MESHES_DATA,
    TUNNEL_MESHES_DATA,
)
from tests.support.api import FakeRedis

##### Fixtures/Fakes ########


@pytest.fixture
def redis_with_inputs():
    fake_redis = FakeRedis()
    fake_redis.hset("files_key", "dem", KARSTNSIM_DEM_BYTES)
    fake_redis.hset("files_key", "voxels", KARSTNSIM_VOXELS_STR)
    for fault_id, data in KARSTNSIM_FAULT_BYTES.items():
        fake_redis.hset("files_key", f"fault_{fault_id}", data)
    return fake_redis


######## Tests ########


def test_compute_tunnel_meshes_writes_each_mesh_to_output_hash(monkeypatch):
    redis = FakeRedis()
    call = {}
    monkeypatch.setattr(tasks, "r", redis)

    def fake_compute_tunnel_meshes(data, metadata):
        call["data"] = data
        call["metadata"] = metadata
        return {"main.off": b"mesh", "service.off": b"service"}

    monkeypatch.setattr(
        tasks.computations, "compute_tunnel_meshes", fake_compute_tunnel_meshes
    )

    result = tasks.compute_tunnel_meshes.run(
        TUNNEL_MESHES_DATA, "output-key", {"request_id": "req-1"}
    )

    assert result == "output-key"
    assert call == {
        "data": TUNNEL_MESHES_DATA,
        "metadata": {"request_id": "req-1"},
    }
    assert redis.hashes["output-key"] == {
        b"main.off": b"mesh",
        b"service.off": b"service",
    }


def test_compute_meshes_consumes_inputs_and_writes_rank_and_fault_hashes(
    monkeypatch,
):
    redis = FakeRedis()
    redis.values.update({"xml-key": b"<xml />", "dem-key": b"dem"})
    call = {}
    monkeypatch.setattr(tasks, "r", redis)

    def fake_compute_meshes(data, xml, dem, metadata):
        call["data"] = data
        call["xml"] = xml
        call["dem"] = dem
        call["metadata"] = metadata
        return {"mesh": {"1": b"unit-1"}, "fault": {"fault-a": b"fault-a"}}

    monkeypatch.setattr(tasks.computations, "compute_meshes", fake_compute_meshes)

    result = tasks.compute_meshes.run(
        MESHES_DATA,
        "xml-key",
        "dem-key",
        "output-key",
        {"project_id": "project-a"},
    )

    assert result == "output-key"
    assert call == {
        "data": MESHES_DATA,
        "xml": b"<xml />",
        "dem": "dem",
        "metadata": {"project_id": "project-a"},
    }
    assert redis.deleted == ["xml-key", "dem-key"]
    assert redis.hashes["output-key"] == {
        b"rank_1": b"unit-1",
        b"fault_fault-a": b"fault-a",
    }


def test_compute_faults_consumes_inputs_and_writes_fault_hashes(monkeypatch):
    redis = FakeRedis()
    redis.values.update({"xml-key": b"<xml />", "dem-key": b"dem"})
    call = {}
    monkeypatch.setattr(tasks, "r", redis)

    def fake_compute_faults(data, xml, dem, metadata):
        call["data"] = data
        call["xml"] = xml
        call["dem"] = dem
        call["metadata"] = metadata
        return {"mesh": {}, "fault": {"fault-a": b"fault-a"}}

    monkeypatch.setattr(tasks.computations, "compute_faults", fake_compute_faults)

    result = tasks.compute_faults.run(
        MESHES_DATA,
        "xml-key",
        "dem-key",
        "output-key",
        {"project_id": "project-b"},
    )

    assert result == "output-key"
    assert call == {
        "data": MESHES_DATA,
        "xml": b"<xml />",
        "dem": "dem",
        "metadata": {"project_id": "project-b"},
    }
    assert redis.deleted == ["xml-key", "dem-key"]
    assert redis.hashes["output-key"] == {b"fault_fault-a": b"fault-a"}


def test_compute_intersections_groups_gwb_meshes_and_serializes_json(monkeypatch):
    redis = FakeRedis()
    redis.values.update({"xml-key": b"<xml />", "dem-key": b"dem"})
    redis.hashes["gwb-key"] = {
        b"7_0": b"gwb-7-a",
        b"7_1": b"gwb-7-b",
        b"8_0": b"gwb-8-a",
    }
    call = {}
    output = {"mesh": {"forCrossSections": {}}, "fault": {"forMaps": {}}}
    monkeypatch.setattr(tasks, "r", redis)

    def fake_compute_intersections(data, xml, dem, gwb_meshes, metadata):
        call["data"] = data
        call["xml"] = xml
        call["dem"] = dem
        call["gwb_meshes"] = dict(gwb_meshes)
        call["metadata"] = metadata
        return output

    monkeypatch.setattr(
        tasks.computations, "compute_intersections", fake_compute_intersections
    )

    result = tasks.compute_intersections.run(
        INTERSECTIONS_DATA,
        "xml-key",
        "dem-key",
        "gwb-key",
        "output-key",
        {"request_id": "req-2"},
    )

    assert result == "output-key"
    assert call == {
        "data": INTERSECTIONS_DATA,
        "xml": b"<xml />",
        "dem": "dem",
        "gwb_meshes": {"7": [b"gwb-7-a", b"gwb-7-b"], "8": [b"gwb-8-a"]},
        "metadata": {"request_id": "req-2"},
    }
    assert redis.deleted == ["xml-key", "dem-key", "gwb-key"]
    assert json.loads(redis.values["output-key"]) == output


def test_compute_intersections_without_hydro_data_does_not_consume_gwb_meshes(
    monkeypatch,
):
    data = {
        "resolution": 25,
        "toCompute": INTERSECTIONS_DATA["toCompute"],
        "computeMap": False,
    }
    redis = FakeRedis()
    redis.values.update({"xml-key": b"<xml />", "dem-key": b"dem"})
    redis.hashes["gwb-key"] = {b"7_0": b"unused-gwb"}
    call = {}
    output = {"mesh": {"forCrossSections": {}}, "fault": {"forMaps": {}}}
    monkeypatch.setattr(tasks, "r", redis)

    def fake_compute_intersections(data, xml, dem, gwb_meshes, metadata):
        call["data"] = data
        call["xml"] = xml
        call["dem"] = dem
        call["gwb_meshes"] = dict(gwb_meshes)
        call["metadata"] = metadata
        return output

    monkeypatch.setattr(
        tasks.computations, "compute_intersections", fake_compute_intersections
    )

    result = tasks.compute_intersections.run(
        data,
        "xml-key",
        "dem-key",
        "gwb-key",
        "output-key",
        {"request_id": "req-no-hydro"},
    )

    assert result == "output-key"
    assert call == {
        "data": data,
        "xml": b"<xml />",
        "dem": "dem",
        "gwb_meshes": {},
        "metadata": {"request_id": "req-no-hydro"},
    }
    assert redis.deleted == ["xml-key", "dem-key"]
    assert redis.hashes["gwb-key"] == {b"7_0": b"unused-gwb"}
    assert json.loads(redis.values["output-key"]) == output


def test_compute_voxels_groups_gwb_meshes_and_serializes_output(monkeypatch):
    redis = FakeRedis()
    redis.values.update({"xml-key": b"<xml />", "dem-key": b"dem"})
    redis.hashes["gwb-key"] = {
        b"7_0": b"gwb-7-a",
        b"7_1": b"gwb-7-b",
        b"8_0": b"gwb-8-a",
    }
    call = {}
    monkeypatch.setattr(tasks, "r", redis)

    def fake_compute_voxels(data, xml, dem, gwb_meshes, metadata):
        call["data"] = data
        call["xml"] = xml
        call["dem"] = dem
        call["gwb_meshes"] = dict(gwb_meshes)
        call["metadata"] = metadata
        return b"vox-output"

    monkeypatch.setattr(tasks.computations, "compute_voxels", fake_compute_voxels)

    result = tasks.compute_voxels.run(
        MESHES_DATA,
        "xml-key",
        "dem-key",
        "gwb-key",
        "output-key",
        {"request_id": "req-3"},
    )

    assert result == "output-key"
    assert call == {
        "data": MESHES_DATA,
        "xml": b"<xml />",
        "dem": "dem",
        "gwb_meshes": {"7": [b"gwb-7-a", b"gwb-7-b"], "8": [b"gwb-8-a"]},
        "metadata": {"request_id": "req-3"},
    }
    assert redis.deleted == ["xml-key", "dem-key", "gwb-key"]
    assert redis.values["output-key"] == b"vox-output"


def test_compute_gwb_meshes_reads_unit_meshes_and_writes_metadata_and_meshes(
    monkeypatch,
):
    redis = FakeRedis()
    redis.hashes["meshes-key"] = {b"1": b"unit-1", b"2": b"unit-2"}
    springs = [{"id": 9, "location": {"x": 1, "y": 2, "z": 3}, "unit_id": 1}]
    call = {}
    output = {
        "metadata": [{"unit_id": 1, "spring_id": 9, "volume": 12.5}],
        "meshes": [b"gwb-a", b"gwb-b"],
    }
    monkeypatch.setattr(tasks, "r", redis)

    def fake_compute_gwb_meshes(unit_meshes, springs_data, metadata):
        call["unit_meshes"] = unit_meshes
        call["springs"] = springs_data
        call["metadata"] = metadata
        return output

    monkeypatch.setattr(
        tasks.computations, "compute_gwb_meshes", fake_compute_gwb_meshes
    )

    result = tasks.compute_gwb_meshes.run(
        springs, "meshes-key", "output-key", {"request_id": "req-4"}
    )

    assert result == "output-key"
    assert call == {
        "unit_meshes": {"1": b"unit-1", "2": b"unit-2"},
        "springs": springs,
        "metadata": {"request_id": "req-4"},
    }
    assert redis.deleted == ["meshes-key"]
    assert redis.hashes["output-key"] == {
        b"metadata": b'[{"unit_id":1,"spring_id":9,"volume":12.5}]',
        b"mesh_0": b"gwb-a",
        b"mesh_1": b"gwb-b",
    }


def test_compute_karstnsim_reads_inputs_and_stores_output(
    monkeypatch, redis_with_inputs
):
    captured = {}
    monkeypatch.setattr(tasks, "r", redis_with_inputs)

    def fake_run(data, dem, voxels, faults, metadata):
        captured["dem"] = dem
        captured["voxels"] = voxels
        captured["faults"] = faults
        return b"output"

    monkeypatch.setattr(tasks, "run_karstnsim", fake_run)

    result = tasks.compute_karstnsim.run(
        KarstNSimData.model_validate(KARSTNSIM_DATA).model_dump_json(),
        "files_key",
        "output_key",
    )

    assert result == "output_key"
    assert captured["dem"] == KARSTNSIM_DEM_BYTES
    assert captured["voxels"] == KARSTNSIM_VOXELS_STR
    assert captured["faults"] == KARSTNSIM_FAULT_BYTES
    assert redis_with_inputs.get("output_key") == b"output"
    assert "files_key" in redis_with_inputs.deleted


def test_compute_karstnsim_handles_missing_faults(monkeypatch):
    redis = FakeRedis()
    redis.hset("files_key", "dem", KARSTNSIM_DEM_BYTES)
    redis.hset("files_key", "voxels", KARSTNSIM_VOXELS_STR)
    monkeypatch.setattr(tasks, "r", redis)

    captured = {}

    def fake_run(data, dem, voxels, faults, metadata):
        captured["faults"] = faults
        return b"output"

    monkeypatch.setattr(tasks, "run_karstnsim", fake_run)

    tasks.compute_karstnsim.run(
        KarstNSimData.model_validate(KARSTNSIM_DATA).model_dump_json(),
        "files_key",
        "output_key",
    )

    assert captured["faults"] == {}
