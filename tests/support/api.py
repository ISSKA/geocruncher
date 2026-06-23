import json
import tarfile
from io import BytesIO
from types import SimpleNamespace
from typing import Any


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


class EagerTask:
    def __init__(self, task, task_id="task-id"):
        self.task = task
        self.task_id = task_id
        self.result = None

    def delay(self, *args):
        self.result = self.task.run(*args)
        return SimpleNamespace(id=self.task_id)


class FakeAsyncResult:
    def __init__(self, task_id=None, state="PENDING", result=None):
        self.task_id = task_id
        self.state = state
        self.result = result
        self.revoked = False

    def get(self):
        return self.result

    def _get_task_meta(self):
        return {"result": self.result}

    def revoke(self, terminate, wait, timeout):
        self.revoked = (terminate, wait, timeout)
        self.state = "REVOKED"


def set_generated_keys(monkeypatch, api_module, *keys):
    remaining = iter(keys)
    monkeypatch.setattr(api_module, "generate_key", lambda: next(remaining))


def set_async_result(monkeypatch, api_module, factory):
    monkeypatch.setattr(api_module, "AsyncResult", factory)


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
