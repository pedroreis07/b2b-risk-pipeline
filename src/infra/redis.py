import atexit
from functools import lru_cache

import redis

from src.config import settings


@lru_cache(maxsize=1)
def create_redis_client() -> redis.Redis:
    pool = redis.BlockingConnectionPool.from_url(
        url=settings.redis_dsn.unicode_string(),
        max_connections=settings.redis_pool_max_size,
        timeout=settings.redis_pool_timeout,
        health_check_interval=settings.redis_health_check_interval,
        socket_timeout=settings.redis_socket_timeout,
        socket_connect_timeout=settings.redis_socket_connect_timeout,
    )
    client = redis.Redis(connection_pool=pool)
    atexit.register(client.close)
    return client
