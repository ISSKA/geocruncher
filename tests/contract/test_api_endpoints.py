import json
import tarfile
from io import BytesIO
from types import SimpleNamespace
from typing import Any

import pytest

import api.api as api_module

######## Fixtures/Fakes ########

MESHES_DATA = {"resolution": {"x": 2, "y": 3, "z": 4}}

BOX = {
    "xmin": 0,
    "ymin": 1,
    "zmin": 2,
    "xmax": 10,
    "ymax": 11,
    "zmax": 12,
}

INTERSECTIONS_DATA = {
    "resolution": 25,
    "toCompute": {"section-a": [BOX]},
    "computeMap": False,
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

GWB_MESHES_DATA = [{"id": 9, "location": {"x": 1, "y": 2, "z": 3}, "unit_id": 1}]


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.hashes = {}
        self.deleted = []

    def set(self, key, value):
        self.values[key] = value if isinstance(value, bytes) else value.encode("utf-8")

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        self.deleted.append(key)
        self.values.pop(key, None)
        self.hashes.pop(key, None)

    def hgetall(self, key):
        return self.hashes.get(key, {})

    def hset(self, key, field, value):
        field_bytes = field if isinstance(field, bytes) else field.encode("utf-8")
        value_bytes = value if isinstance(value, bytes) else value.encode("utf-8")
        self.hashes.setdefault(key, {})[field_bytes] = value_bytes


class FakeTask:
    def __init__(self, task_id="task-id"):
        self.task_id = task_id
        self.calls = []

    def delay(self, *args):
        self.calls.append(args)
        return SimpleNamespace(id=self.task_id)


class FakeAsyncResult:
    def __init__(self, state="PENDING", result=None):
        self.state = state
        self.result = result
        self.revoked = False

    def get(self):
        return self.result

    def revoke(self, terminate, wait, timeout):
        self.revoked = (terminate, wait, timeout)
        self.state = "REVOKED"


@pytest.fixture
def client():
    api_module.app.config.update(TESTING=True)
    return api_module.app.test_client()


@pytest.fixture
def fake_redis(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(api_module, "r", redis)
    return redis


def set_generated_keys(monkeypatch, *keys):
    remaining = iter(keys)
    monkeypatch.setattr(api_module, "generate_key", lambda: next(remaining))


def multipart_with_files(payload, metadata=None, **files):
    data: dict[str, Any] = {"data": json.dumps(payload)}
    if metadata is not None:
        data["metadata"] = json.dumps(metadata)
    for field, content in files.items():
        data[field] = (BytesIO(content), f"{field}.dat")
    return data


def tar_entries(response):
    with tarfile.open(fileobj=BytesIO(response.data), mode="r") as tar:
        entries = {}
        for member in tar.getmembers():
            if not member.isfile():
                continue
            extracted = tar.extractfile(member)
            assert extracted is not None
            entries[member.name] = extracted.read()
        return entries


######## Tests ########


def test_filemap_to_tar_roundtrips_binary_files():
    output = api_module.filemap_to_tar(
        {b"unit/rank_1.off": b"OFF data", b"fault_a.off": b"fault"}
    )

    with tarfile.open(fileobj=output, mode="r") as tar:
        assert tar.getnames() == ["unit/rank_1.off", "fault_a.off"]
        unit_file = tar.extractfile("unit/rank_1.off")
        fault_file = tar.extractfile("fault_a.off")
        assert unit_file is not None
        assert fault_file is not None
        assert unit_file.read() == b"OFF data"
        assert fault_file.read() == b"fault"


def test_post_tunnel_meshes_valid_data_queues_task(client, monkeypatch):
    task = FakeTask("tunnel-task")
    set_generated_keys(monkeypatch, "output-key")
    monkeypatch.setattr(api_module.tasks, "compute_tunnel_meshes", task)

    response = client.post(
        "/compute/tunnel_meshes",
        data=multipart_with_files(
            TUNNEL_MESHES_DATA, metadata={"project_id": "project-a"}
        ),
    )

    assert response.status_code == 202
    assert response.text == "tunnel-task"
    assert task.calls == [
        (TUNNEL_MESHES_DATA, "output-key", {"project_id": "project-a"})
    ]


@pytest.mark.parametrize(
    "path",
    [
        "/compute/tunnel_meshes",
        "/compute/meshes",
        "/compute/faults",
        "/compute/intersections",
        "/compute/voxels",
        "/compute/gwb_meshes",
    ],
)
def test_post_endpoints_invalid_json_returns_400(client, path):
    response = client.post(path, data={"data": "{not-json"})

    assert response.status_code == 400
    assert response.mimetype == "application/json"


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/compute/meshes", MESHES_DATA),
        ("/compute/faults", MESHES_DATA),
        ("/compute/intersections", INTERSECTIONS_DATA),
        ("/compute/voxels", MESHES_DATA),
    ],
)
def test_post_project_file_endpoints_require_xml_and_dem(client, path, payload):
    response = client.post(path, data={"data": json.dumps(payload)})

    assert response.status_code == 400
    assert response.text == "Missing xml or dem file"


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/compute/meshes", MESHES_DATA),
        ("/compute/faults", MESHES_DATA),
        ("/compute/intersections", INTERSECTIONS_DATA),
        ("/compute/voxels", MESHES_DATA),
    ],
)
@pytest.mark.parametrize(
    "files",
    [
        {"xml": b"<xml />"},
        {"dem": b"dem"},
    ],
    ids=["missing-dem", "missing-xml"],
)
def test_post_project_file_endpoints_reject_partial_uploads(
    client, path, payload, files
):
    response = client.post(path, data=multipart_with_files(payload, **files))

    assert response.status_code == 400
    assert response.text == "Missing xml or dem file"


@pytest.mark.parametrize(
    ("path", "task_name"),
    [
        ("/compute/meshes", "compute_meshes"),
        ("/compute/faults", "compute_faults"),
    ],
)
def test_post_meshes_and_faults_store_inputs_and_queue_task(
    client, fake_redis, monkeypatch, path, task_name
):
    task = FakeTask(f"{task_name}-id")
    metadata = {"request_id": "req-1"}
    set_generated_keys(monkeypatch, "xml-key", "dem-key", "output-key")
    monkeypatch.setattr(api_module.tasks, task_name, task)

    response = client.post(
        path,
        data=multipart_with_files(
            MESHES_DATA,
            metadata=metadata,
            xml=b"<xml />",
            dem=b"ncols 1\n",
        ),
    )

    assert response.status_code == 202
    assert response.text == f"{task_name}-id"
    assert fake_redis.values == {
        "xml-key": b"<xml />",
        "dem-key": b"ncols 1\n",
    }
    assert task.calls == [(MESHES_DATA, "xml-key", "dem-key", "output-key", metadata)]


@pytest.mark.parametrize(
    ("path", "payload", "task_name"),
    [
        ("/compute/intersections", INTERSECTIONS_DATA, "compute_intersections"),
        ("/compute/voxels", MESHES_DATA, "compute_voxels"),
    ],
)
def test_post_hydro_aware_endpoints_store_gwb_meshes_and_queue_task(
    client, fake_redis, monkeypatch, path, payload, task_name
):
    task = FakeTask(f"{task_name}-id")
    metadata = {"project_id": "project-b"}
    set_generated_keys(monkeypatch, "xml-key", "dem-key", "gwb-key", "output-key")
    monkeypatch.setattr(api_module.tasks, task_name, task)

    response = client.post(
        path,
        data=multipart_with_files(
            payload,
            metadata=metadata,
            xml=b"<xml />",
            dem=b"dem",
            **{"7_0": b"gwb-a", "7_1": b"gwb-b"},
        ),
    )

    assert response.status_code == 202
    assert response.text == f"{task_name}-id"
    assert fake_redis.values == {"xml-key": b"<xml />", "dem-key": b"dem"}
    assert fake_redis.hashes["gwb-key"] == {
        b"7_0": b"gwb-a",
        b"7_1": b"gwb-b",
    }
    assert task.calls == [
        (payload, "xml-key", "dem-key", "gwb-key", "output-key", metadata)
    ]


def test_post_gwb_meshes_stores_unit_meshes_and_queues_task(
    client, fake_redis, monkeypatch
):
    task = FakeTask("gwb-task")
    metadata = {"request_id": "req-gwb"}
    set_generated_keys(monkeypatch, "meshes-key", "output-key")
    monkeypatch.setattr(api_module.tasks, "compute_gwb_meshes", task)

    response = client.post(
        "/compute/gwb_meshes",
        data=multipart_with_files(
            GWB_MESHES_DATA,
            metadata=metadata,
            **{"1": b"unit-1", "2": b"unit-2"},
        ),
    )

    assert response.status_code == 202
    assert response.text == "gwb-task"
    assert fake_redis.hashes["meshes-key"] == {
        b"1": b"unit-1",
        b"2": b"unit-2",
    }
    assert task.calls == [(GWB_MESHES_DATA, "meshes-key", "output-key", metadata)]


@pytest.mark.parametrize(
    "path",
    [
        "/compute/tunnel_meshes",
        "/compute/meshes",
        "/compute/faults",
        "/compute/intersections",
        "/compute/voxels",
        "/compute/gwb_meshes",
    ],
)
def test_get_compute_endpoints_require_id(client, path):
    response = client.get(path)

    assert response.status_code == 400
    assert response.text == "Missing parameter id"


@pytest.mark.parametrize(
    "path",
    [
        "/compute/tunnel_meshes",
        "/compute/meshes",
        "/compute/faults",
        "/compute/intersections",
        "/compute/voxels",
        "/compute/gwb_meshes",
    ],
)
def test_get_compute_endpoints_return_non_success_state(client, monkeypatch, path):
    monkeypatch.setattr(
        api_module.celery,
        "AsyncResult",
        lambda task_id: FakeAsyncResult(state="PENDING"),
    )

    response = client.get(path, query_string={"id": "task-id"})

    assert response.status_code == 200
    assert response.text == "PENDING"


@pytest.mark.parametrize(
    ("path", "storage"),
    [
        ("/compute/tunnel_meshes", "hash"),
        ("/compute/meshes", "hash"),
        ("/compute/faults", "hash"),
        ("/compute/intersections", "value"),
        ("/compute/voxels", "value"),
        ("/compute/gwb_meshes", "hash"),
    ],
)
def test_get_compute_endpoints_return_204_for_empty_success_output(
    client, fake_redis, monkeypatch, path, storage
):
    monkeypatch.setattr(
        api_module.celery,
        "AsyncResult",
        lambda task_id: FakeAsyncResult(state="SUCCESS", result="output-key"),
    )
    if storage == "hash":
        fake_redis.hashes["output-key"] = {}
    else:
        fake_redis.values["output-key"] = b""

    response = client.get(path, query_string={"id": "task-id"})

    assert response.status_code == 204
    assert fake_redis.deleted == ["output-key"]


@pytest.mark.parametrize(
    "path",
    [
        "/compute/tunnel_meshes",
        "/compute/meshes",
        "/compute/faults",
        "/compute/gwb_meshes",
    ],
)
def test_get_tar_compute_endpoints_return_tar_and_delete_output(
    client, fake_redis, monkeypatch, path
):
    fake_redis.hashes["output-key"] = {b"a.off": b"mesh-a", b"b.off": b"mesh-b"}
    monkeypatch.setattr(
        api_module.celery,
        "AsyncResult",
        lambda task_id: FakeAsyncResult(state="SUCCESS", result="output-key"),
    )

    response = client.get(path, query_string={"id": "task-id"})

    assert response.status_code == 200
    assert response.mimetype == "application/x-tar"
    assert tar_entries(response) == {"a.off": b"mesh-a", "b.off": b"mesh-b"}
    assert fake_redis.deleted == ["output-key"]


def test_get_intersections_returns_json_and_deletes_output(
    client, fake_redis, monkeypatch
):
    fake_redis.values["output-key"] = b'{"mesh":{},"fault":{}}'
    monkeypatch.setattr(
        api_module.celery,
        "AsyncResult",
        lambda task_id: FakeAsyncResult(state="SUCCESS", result="output-key"),
    )

    response = client.get("/compute/intersections", query_string={"id": "task-id"})

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert response.text == '{"mesh":{},"fault":{}}'
    assert fake_redis.deleted == ["output-key"]


def test_get_voxels_returns_text_and_deletes_output(client, fake_redis, monkeypatch):
    fake_redis.values["output-key"] = b"vox-data"
    monkeypatch.setattr(
        api_module.celery,
        "AsyncResult",
        lambda task_id: FakeAsyncResult(state="SUCCESS", result="output-key"),
    )

    response = client.get("/compute/voxels", query_string={"id": "task-id"})

    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert response.text == "vox-data"
    assert fake_redis.deleted == ["output-key"]


def test_poll_returns_states_for_many_tasks(client, monkeypatch):
    states = {"task-a": "PENDING", "task-b": "SUCCESS"}
    monkeypatch.setattr(
        api_module.celery,
        "AsyncResult",
        lambda task_id: FakeAsyncResult(state=states[task_id]),
    )

    response = client.post("/poll", json=["task-a", "task-b"])

    assert response.status_code == 200
    assert response.json == states


def test_revoke_requires_id(client):
    response = client.post("/revoke")

    assert response.status_code == 400
    assert response.text == "Missing parameter id"


def test_revoke_terminates_task_and_returns_success(client, monkeypatch):
    result = FakeAsyncResult(state="STARTED")
    monkeypatch.setattr(api_module.celery, "AsyncResult", lambda task_id: result)

    response = client.post("/revoke", query_string={"id": "task-id"})

    assert response.status_code == 200
    assert response.text == "Task task-id revoked"
    assert result.revoked == (True, True, 2)


def test_revoke_returns_500_when_task_cannot_be_revoked(client, monkeypatch):
    class NotRevokedResult(FakeAsyncResult):
        def revoke(self, terminate, wait, timeout):
            self.revoked = (terminate, wait, timeout)
            self.state = "STARTED"

    monkeypatch.setattr(
        api_module.celery,
        "AsyncResult",
        lambda task_id: NotRevokedResult(state="STARTED"),
    )

    response = client.post("/revoke", query_string={"id": "task-id"})

    assert response.status_code == 500
    assert response.text == "Task task-id could not be revoked"
