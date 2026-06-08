import json
import uuid
from typing import Any, cast

import redis
from flask import request

from geocruncher.profiler import ProfilerMetadata


def parse_metadata_from_request() -> ProfilerMetadata | None:
    """Parse optional metadata from Flask request.

    Looks for 'metadata' form field and parses as JSON

    Returns
    -------
    ProfilerMetadata | None
        Parsed metadata dictionary, or None if not provided or invalid
    """
    if hasattr(request, "form") and "metadata" in request.form:
        try:
            metadata = json.loads(request.form["metadata"])
        except (json.JSONDecodeError, ValueError):
            return None

        if isinstance(metadata, dict) and all(isinstance(key, str) for key in metadata):
            return cast(ProfilerMetadata, metadata)

    return None


def get_and_delete(r: redis.client.Redis, key: str) -> bytes:
    """Get a key from the Redis Client, then delete it, and raise a ValueError if it doesn't exist.

    Parameters
    ----------
    r : redis.client.Redis
        The Redis Client.
    key : str
        The key to try to read then delete.

    Returns
    -------
    bytes
        The value.
    """
    data = r.get(key)
    if data is None:
        raise ValueError(f"Key not found {key}")
    r.delete(key)
    return cast(bytes, data)


def get_bytes(r: redis.client.Redis, key: str) -> bytes | None:
    """Get a binary value from Redis."""
    return cast(bytes | None, r.get(key))


def get_hash_bytes(r: redis.client.Redis, key: str) -> dict[bytes, bytes]:
    """Get a binary hash from Redis."""
    return cast(dict[bytes, bytes], r.hgetall(key))


def hset_bytes(r: redis.client.Redis, key: str, field: str, value: bytes) -> None:
    """Store a binary value in a Redis hash."""
    r.hset(key, field, cast(Any, value))


def generate_key() -> str:
    """Generate a pseudo-random unique string key, for use with Redis.

    Returns
    -------
    str
        The generated key.
    """
    return uuid.uuid4().hex
