import json
import re
from typing import cast

import pytest
from flask import Flask
from redis.client import Redis

import api.utils as utils
from tests.support.api import FakeRedis


def test_parse_metadata_from_request_returns_valid_json_object():
    app = Flask(__name__)
    metadata = {"request_id": "abc", "attempt": 2}

    with app.test_request_context(
        "/",
        method="POST",
        data={"metadata": json.dumps(metadata)},
    ):
        assert utils.parse_metadata_from_request() == metadata


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        "{not-json",
        "[1, 2, 3]",
    ],
)
def test_parse_metadata_from_request_returns_none_for_missing_or_invalid_metadata(
    metadata,
):
    app = Flask(__name__)
    data = {} if metadata is None else {"metadata": metadata}

    with app.test_request_context("/", method="POST", data=data):
        assert utils.parse_metadata_from_request() is None


def test_get_and_delete_returns_value_and_deletes_key():
    redis = FakeRedis()
    redis.values["key"] = b"value"

    assert utils.get_and_delete(cast(Redis, redis), "key") == b"value"

    assert redis.deleted == ["key"]
    assert "key" not in redis.values


def test_get_and_delete_raises_for_missing_key():
    with pytest.raises(ValueError, match="Key not found missing"):
        utils.get_and_delete(cast(Redis, FakeRedis()), "missing")


def test_binary_redis_helpers_read_and_write_values():
    redis = FakeRedis()
    redis.values["blob"] = b"abc"

    assert utils.get_bytes(cast(Redis, redis), "blob") == b"abc"
    assert utils.get_bytes(cast(Redis, redis), "missing") is None

    utils.hset_bytes(cast(Redis, redis), "hash", "field", b"value")

    assert utils.get_hash_bytes(cast(Redis, redis), "hash") == {b"field": b"value"}


def test_generate_key_returns_unique_uuid_hex_strings():
    keys = {utils.generate_key() for _ in range(100)}

    assert len(keys) == 100
    assert all(re.fullmatch(r"[0-9a-f]{32}", key) for key in keys)
