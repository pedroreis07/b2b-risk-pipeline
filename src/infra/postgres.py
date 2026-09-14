import atexit
import logging
from functools import lru_cache

from psycopg import Connection
from psycopg_pool import ConnectionPool

from src.config import settings


logger = logging.getLogger(__name__)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_audit_log (
    batch_id UUID PRIMARY KEY,
    status VARCHAR(50) NOT NULL,
    file VARCHAR(255) NOT NULL,
    total_rows INT NOT NULL DEFAULT 0,
    duration_seconds NUMERIC(6, 2) DEFAULT 0.0,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    finished_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS transactions_risk_analysis (
    transaction_id UUID NOT NULL,
    payer_cnpj VARCHAR(14) NOT NULL,
    receiver_cnpj VARCHAR(14) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    payer_status VARCHAR(100) NOT NULL,
    receiver_status VARCHAR(100) NOT NULL,
    payer_company_age NUMERIC(5, 2) NOT NULL,
    receiver_company_age NUMERIC(5, 2) NOT NULL,
    payer_capital_stock NUMERIC(19, 2) NOT NULL,
    risk_score INTEGER NOT NULL,
    score_reasons JSONB NOT NULL,
    payload_hash UUID NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT pk_transaction_payload PRIMARY KEY (transaction_id, payload_hash)
);
"""


@lru_cache(maxsize=1)
def create_postgres_pool() -> ConnectionPool[Connection]:
    pg_pool_min_size = 0
    pg_pool_max_size = 1

    logger.info(
        "Creating PostgreSQL pool (min=%d, max=%d, max_idle=%ds)",
        pg_pool_min_size,
        pg_pool_max_size,
        settings.pg_pool_max_idle,
    )
    pool: ConnectionPool[Connection] = ConnectionPool(
        conninfo=settings.pg_dsn.unicode_string(),
        max_size=pg_pool_max_size,
        min_size=pg_pool_min_size,
        check=ConnectionPool.check_connection,
        max_idle=settings.pg_pool_max_idle,
        open=True,
    )

    atexit.register(lambda: (logger.info("Closing Postgres pool"), pool.close()))
    return pool


def ensure_schema() -> None:
    pool = create_postgres_pool()
    with pool.connection() as conn, conn.transaction():
        conn.execute(SCHEMA_SQL)
    logger.info("Database schema verified/created")
