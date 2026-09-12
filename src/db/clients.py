import redis

from src.config import settings


def create_redis_client() -> redis.Redis:
    pool = redis.ConnectionPool.from_url(url=settings.redis_dsn.unicode_string())
    return redis.Redis(connection_pool=pool)
