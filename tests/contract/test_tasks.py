import json
from unittest.mock import patch

import pytest

import api.tasks as tasks
from tests.support.api import FakeRedis

##### Fixtures/Fakes ########

MESHES_DATA = {"resolution": {"x": 2, "y": 3, "z": 4}}

INTERSECTIONS_DATA = {
    "resolution": 25,
    "toCompute": {
        "section-a": [
            {
                "xmin": 0,
                "ymin": 1,
                "zmin": 2,
                "xmax": 10,
                "ymax": 11,
                "zmax": 12,
            }
        ]
    },
    "computeMap": False,
    "springs": {"7": {"x": 1, "y": 2, "z": 3}},
}

TUNNEL_MESHES_DATA = {
    "tunnels": [
        {
            "name": "main",
            "shape": "Circle",
            "functions": [{"x": "t", "y": "0", "z": "0"}],
            "radius": 2.0,
        }
    ],
    "nb_vertices": 8,
    "step": 0.5,
    "idxStart": -1,
    "idxEnd": -1,
    "tStart": 0.0,
    "tEnd": 1.0,
}


@pytest.fixture
def redis_with_inputs(
    karstnsim_dem_bytes,
    karstnsim_voxels_str,
    karstnsim_fault_bytes,
):
    fake_redis = FakeRedis()
    fake_redis.hset("files_key", "dem", karstnsim_dem_bytes)
    fake_redis.hset("files_key", "voxels", karstnsim_voxels_str)
    for fault_id, data in karstnsim_fault_bytes.items():
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


class TestComputeKarstNSimTask:
    def test_reads_inputs(
        self,
        redis_with_inputs,
        karstnsim_data_dict,
        karstnsim_dem_bytes,
        karstnsim_voxels_str,
        karstnsim_fault_bytes,
    ):
        from api.tasks import compute_karstnsim
        from geocruncher.karstnsim.models import KarstNSimData

        captured = {}

        def fake_run(data, dem, voxels, faults, metadata):
            captured["dem"] = dem
            captured["voxels"] = voxels
            captured["faults"] = faults
            return b"output"

        with (
            patch("api.tasks.r", redis_with_inputs),
            patch(
                "api.tasks.run_karstnsim",
                side_effect=fake_run,
            ),
        ):
            compute_karstnsim(
                KarstNSimData.model_validate(karstnsim_data_dict),
                "files_key",
                "output_key",
            )

        assert captured["dem"] == karstnsim_dem_bytes
        assert captured["voxels"] == karstnsim_voxels_str
        assert captured["faults"] == karstnsim_fault_bytes

    def test_stores_output(
        self,
        redis_with_inputs,
        karstnsim_data_dict,
    ):
        from api.tasks import compute_karstnsim
        from geocruncher.karstnsim.models import KarstNSimData

        output = b"# Run info\n{}\n# Data\n"

        with (
            patch("api.tasks.r", redis_with_inputs),
            patch(
                "api.tasks.run_karstnsim",
                return_value=output,
            ),
        ):
            key = compute_karstnsim(
                KarstNSimData.model_validate(karstnsim_data_dict),
                "files_key",
                "output_key",
            )

        assert key == "output_key"
        assert redis_with_inputs.hashes["output_key"][b"output.txt"] == output

    def test_deletes_input_hash(
        self,
        redis_with_inputs,
        karstnsim_data_dict,
    ):
        from api.tasks import compute_karstnsim
        from geocruncher.karstnsim.models import KarstNSimData

        with (
            patch("api.tasks.r", redis_with_inputs),
            patch(
                "api.tasks.run_karstnsim",
                return_value=b"output",
            ),
        ):
            compute_karstnsim(
                KarstNSimData.model_validate(karstnsim_data_dict),
                "files_key",
                "output_key",
            )

        assert "files_key" in redis_with_inputs.deleted

    def test_parses_fault_ids(
        self,
        redis_with_inputs,
        karstnsim_data_dict,
        karstnsim_fault_bytes,
    ):
        from api.tasks import compute_karstnsim
        from geocruncher.karstnsim.models import KarstNSimData

        captured = {}

        def fake_run(data, dem, voxels, faults, metadata):
            captured.update(faults)
            return b"output"

        with (
            patch("api.tasks.r", redis_with_inputs),
            patch(
                "api.tasks.run_karstnsim",
                side_effect=fake_run,
            ),
        ):
            compute_karstnsim(
                KarstNSimData.model_validate(karstnsim_data_dict),
                "files_key",
                "output_key",
            )

        assert captured == karstnsim_fault_bytes
