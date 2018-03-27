from redis import StrictRedis
from . import config

redis_conn = StrictRedis.from_url(config.REDIS)
