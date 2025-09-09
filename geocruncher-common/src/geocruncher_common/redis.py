import os
from typing import Awaitable
import redis

class RedisClient(redis.StrictRedis):
    
    def hgetall(self, name: str) -> dict:
        return super().hgetall(name) # type: ignore

redis_client = RedisClient(
    host=os.environ['REDIS_HOST'], port=6379, db=0, )
