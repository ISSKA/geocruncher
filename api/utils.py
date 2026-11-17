import json
import uuid
from typing import Any, cast

import redis
from flask import request

from geocruncher.profiler import ProfilerMetadata


def gwb_part_count() -> int:
    """Count groundwater-body parts in the uploaded mesh fields."""
    ids = {key.split("_", 1)[0] for key in request.files if key not in {"model", "dem"}}
    return len(ids)


def uploaded_mesh_features() -> dict[str, int | float]:
    """Return byte-size features for uploaded groundwater-body meshes."""
    sizes = []
    for key, file in request.files.items():
        if key in {"model", "dem"}:
            continue
        position = file.stream.tell()
        content = file.read()
        file.stream.seek(position)
        sizes.append(len(content))

    total = sum(sizes)
    return {
        "total_mesh_bytes": total,
        "mesh_bytes_per_unit": total / len(sizes) if sizes else 0,
    }


def sum_estimates(estimates: list[dict]) -> dict:
    """Sum duration ranges, such as estimates for multiple tunnels."""
    keys = ("lower", "p10", "p50", "p90", "upper")
    if len(estimates) == 1:
        return {key: estimates[0][key] for key in keys}
    return {key: sum(estimate[key] for estimate in estimates) for key in keys}


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
