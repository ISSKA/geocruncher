import json
from types import SimpleNamespace

import pytest

from tests.support.api import (
    EagerTask,
    FakeAsyncResult,
    FakeRedis,
    multipart_with_files,
    set_async_result,
    set_generated_keys,
    tar_entries,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.native,
]


@pytest.fixture
def api_harness(computations, mesh_io, monkeypatch):
    api_module = pytest.importorskip("api.api")
    task_module = pytest.importorskip("api.tasks")

    redis = FakeRedis()
    monkeypatch.setattr(api_module, "r", redis)
    monkeypatch.setattr(task_module, "r", redis)
    monkeypatch.setattr(task_module, "set_current_task", lambda task: None)
    api_module.app.config.update(TESTING=True)
    return SimpleNamespace(
        api_module=api_module,
        task_module=task_module,
        computations=computations,
        mesh_io=mesh_io,
        redis=redis,
        client=api_module.app.test_client(),
    )


def _install_eager_task(monkeypatch, api_harness, task_name, *keys):
    eager_task = EagerTask(getattr(api_harness.task_module, task_name))
    set_generated_keys(monkeypatch, api_harness.api_module, *keys)
    monkeypatch.setattr(api_harness.api_module.tasks, task_name, eager_task)
    set_async_result(
        monkeypatch,
        api_harness.api_module,
        lambda task_id: FakeAsyncResult(
            task_id=task_id, state="SUCCESS", result=eager_task.result
        ),
    )
    return eager_task


######## Tests ########


def test_tunnel_meshes_endpoint_runs_eager_task_and_returns_tar(
    api_harness, decode_meshes, fixture_json, monkeypatch
):
    eager_task = _install_eager_task(
        monkeypatch, api_harness, "compute_tunnel_meshes", "output-key"
    )

    post_response = api_harness.client.post(
        "/compute/tunnel_meshes",
        data={"data": json.dumps(fixture_json("tunnel.json"))},
    )

    assert post_response.status_code == 202
    assert post_response.text == "task-id"
    assert eager_task.result == "output-key"

    get_response = api_harness.client.get(
        "/compute/tunnel_meshes", query_string={"id": "task-id"}
    )
    entries = tar_entries(get_response)

    assert get_response.status_code == 200
    assert get_response.mimetype == "application/x-tar"
    assert set(entries) == {"circle_tunnel", "rectangle_tunnel", "elliptic_tunnel"}
    decode_meshes(entries)
    assert "output-key" in api_harness.redis.deleted


def test_meshes_endpoint_runs_eager_task_and_returns_tar(
    api_harness, decode_meshes, fixture_bytes, fixture_json, protobuf_model, monkeypatch
):
    eager_task = _install_eager_task(
        monkeypatch,
        api_harness,
        "compute_meshes",
        "model-key",
        "dem-key",
        "output-key",
    )

    post_response = api_harness.client.post(
        "/compute/meshes",
        data=multipart_with_files(
            fixture_json("mesh.json"),
            model=protobuf_model,
            dem=fixture_bytes("geocruncher_dem.asc"),
        ),
    )

    assert post_response.status_code == 202
    assert post_response.text == "task-id"
    assert eager_task.result == "output-key"

    get_response = api_harness.client.get(
        "/compute/meshes", query_string={"id": "task-id"}
    )
    entries = tar_entries(get_response)

    assert get_response.status_code == 200
    assert get_response.mimetype == "application/x-tar"
    assert "rank_1" in entries
    assert "fault_topography" in entries
    decode_meshes(entries)
    assert "output-key" in api_harness.redis.deleted


def test_faults_endpoint_runs_eager_task_and_returns_tar(
    api_harness, decode_meshes, fixture_bytes, fixture_json, protobuf_model, monkeypatch
):
    eager_task = _install_eager_task(
        monkeypatch,
        api_harness,
        "compute_faults",
        "model-key",
        "dem-key",
        "output-key",
    )

    post_response = api_harness.client.post(
        "/compute/faults",
        data=multipart_with_files(
            fixture_json("mesh.json"),
            model=protobuf_model,
            dem=fixture_bytes("geocruncher_dem.asc"),
        ),
    )

    assert post_response.status_code == 202
    assert post_response.text == "task-id"
    assert eager_task.result == "output-key"

    get_response = api_harness.client.get(
        "/compute/faults", query_string={"id": "task-id"}
    )
    entries = tar_entries(get_response)

    assert get_response.status_code == 200
    assert get_response.mimetype == "application/x-tar"
    assert set(entries) == {"fault_topography"}
    decode_meshes(entries)
    assert "output-key" in api_harness.redis.deleted


def test_intersections_endpoint_runs_eager_task_and_returns_json(
    api_harness, fixture_bytes, fixture_json, protobuf_model, monkeypatch
):
    eager_task = _install_eager_task(
        monkeypatch,
        api_harness,
        "compute_intersections",
        "model-key",
        "dem-key",
        "gwb-key",
        "output-key",
    )
    data = fixture_json("intersection_hydro.json")
    section_id = next(iter(data["toCompute"]))

    post_response = api_harness.client.post(
        "/compute/intersections",
        data=multipart_with_files(
            data,
            model=protobuf_model,
            dem=fixture_bytes("geocruncher_dem.asc"),
            **{"7_0": fixture_bytes("gwb_meshes/7.off")},
        ),
    )

    assert post_response.status_code == 202
    assert post_response.text == "task-id"
    assert eager_task.result == "output-key"

    get_response = api_harness.client.get(
        "/compute/intersections", query_string={"id": "task-id"}
    )
    payload = json.loads(get_response.text)
    matrix_gwb = payload["mesh"]["matrixGwb"][section_id][0]

    assert get_response.status_code == 200
    assert get_response.mimetype == "application/json"
    assert set(payload) == {"mesh", "fault"}
    assert set(payload["mesh"]["springs"][section_id][0]) == {"spring-1"}
    assert set(payload["mesh"]["drillholes"][section_id][0]) == {"drillhole-1"}
    assert set(matrix_gwb) == {0, 7}
    assert "output-key" in api_harness.redis.deleted


def test_voxels_endpoint_runs_eager_task_and_returns_text(
    api_harness, fixture_bytes, fixture_json, protobuf_model, monkeypatch
):
    eager_task = _install_eager_task(
        monkeypatch,
        api_harness,
        "compute_voxels",
        "model-key",
        "dem-key",
        "gwb-key",
        "output-key",
    )

    post_response = api_harness.client.post(
        "/compute/voxels",
        data=multipart_with_files(
            fixture_json("mesh.json"),
            model=protobuf_model,
            dem=fixture_bytes("geocruncher_dem.asc"),
        ),
    )

    assert post_response.status_code == 202
    assert post_response.text == "task-id"
    assert eager_task.result == "output-key"

    get_response = api_harness.client.get(
        "/compute/voxels", query_string={"id": "task-id"}
    )
    lines = get_response.text.splitlines()

    assert get_response.status_code == 200
    assert get_response.mimetype == "text/plain"
    assert "NUMBERX=5" in lines[0]
    assert "NUMBERY=5" in lines[0]
    assert "NUMBERZ=5" in lines[0]
    assert lines[1] == "rank gwb_id"
    assert len(lines[2:]) == 125
    assert "output-key" in api_harness.redis.deleted


def test_gwb_meshes_endpoint_runs_eager_task_and_returns_tar(
    api_harness,
    decode_meshes,
    fixture_json,
    fixture_text,
    protobuf_model,
    monkeypatch,
):
    eager_task = _install_eager_task(
        monkeypatch,
        api_harness,
        "compute_gwb_meshes",
        "meshes-key",
        "output-key",
    )
    springs = fixture_json("gwb_spring.json")
    unit_meshes = api_harness.computations.compute_meshes(
        fixture_json("mesh.json"),
        protobuf_model,
        fixture_text("geocruncher_dem.asc"),
    )["mesh"]

    post_response = api_harness.client.post(
        "/compute/gwb_meshes",
        data=multipart_with_files(
            springs,
            **unit_meshes,
        ),
    )

    assert post_response.status_code == 202
    assert post_response.text == "task-id"
    assert eager_task.result == "output-key"

    get_response = api_harness.client.get(
        "/compute/gwb_meshes", query_string={"id": "task-id"}
    )
    entries = tar_entries(get_response)
    metadata = json.loads(entries.pop("metadata"))

    assert get_response.status_code == 200
    assert get_response.mimetype == "application/x-tar"
    assert len(metadata) == 1
    assert metadata[0]["unit_id"] == 1
    assert metadata[0]["spring_id"] == 1
    assert metadata[0]["volume"] > 0
    assert set(entries) == {"mesh_0"}
    decode_meshes(entries)
    assert "output-key" in api_harness.redis.deleted
