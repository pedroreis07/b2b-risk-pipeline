import atexit
from functools import lru_cache

import redis
from psycopg import Connection
from psycopg_pool import ConnectionPool

from src.config import settings


QUERY = """
CREATE TABLE IF NOT EXISTS transactions_risk_analysis (
    transaction_id VARCHAR(100) NOT NULL,
    payer_cnpj VARCHAR(14) NOT NULL,
    receiver_cnpj VARCHAR(14) NOT NULL,
    amount NUMERIC(15, 2),
    payer_status VARCHAR(100),
    receiver_status VARCHAR(100),
    payer_company_age NUMERIC(5, 2),
    receiver_company_age NUMERIC(5, 2),
    payer_capital_stock NUMERIC(19, 2),
    risk_score INTEGER,
    score_reasons JSONB,
    payload_hash NUMERIC(20, 0),
    processed_at TIMESTAMP WITH TIME ZONE
);
"""


@lru_cache(maxsize=1)
def create_postgres_pool() -> ConnectionPool[Connection]:
    pool: ConnectionPool[Connection] = ConnectionPool(
        conninfo=settings.pg_dsn.unicode_string(),
        max_size=settings.pg_pool_max_size,
        min_size=settings.pg_pool_min_size,
        check=ConnectionPool.check_connection,
        max_idle=settings.pg_pool_max_idle,
        open=True,
    )
    atexit.register(pool.close)
    return pool


def ensure_schema(pool: ConnectionPool[Connection]) -> None:
    with pool.connection() as conn, conn.transaction():
        conn.execute(QUERY)


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
