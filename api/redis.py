import os
import redis

redis_client = redis.StrictRedis(
    host=os.environ['REDIS_HOST'], port=6379, db=0, )
