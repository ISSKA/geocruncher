import uuid
import redis
import json
from flask import request
from typing import Optional, Dict, Any


def parse_metadata_from_request() -> Optional[Dict[str, Any]]:
    """Parse optional metadata from Flask request.
    
    Looks for 'metadata' form field and parses as JSON
    
    Returns
    -------
    Optional[Dict[str, Any]]
        Parsed metadata dictionary, or None if not provided or invalid
    """
    if hasattr(request, 'form') and 'metadata' in request.form:
        try:
            return json.loads(request.form['metadata'])
        except (json.JSONDecodeError, ValueError):
            return None
    
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
    str
        The value.
    """
    data = r.get(key)
    if data is None:
        raise ValueError(f"Key not found {key}")
    r.delete(key)
    return data


def generate_key() -> str:
    """Generate a pseudo-random unique string key, for use with Redis.

    Returns
    -------
    str
        The generated key.
    """
    return uuid.uuid4().hex
