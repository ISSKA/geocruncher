import os
from typing import Any
import redis
from redis.typing import KeyT

# Override to fix annoying typing issue in redis-py
# while waiting for https://github.com/redis/redis-py/pull/3619
class RedisClient(redis.StrictRedis):

    def get(self, name: KeyT) -> Any:
        return super().get(name)
    
    def hgetall(self, name: str) -> dict:
        return super().hgetall(name) # type: ignore

redis_client = RedisClient(
    host=os.environ['REDIS_HOST'], port=6379, db=0, )
