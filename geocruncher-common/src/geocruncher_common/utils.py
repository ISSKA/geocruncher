import uuid
from .redis import RedisClient

def get_and_delete(r: RedisClient, key: str) -> bytes:
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
