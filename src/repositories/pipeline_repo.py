import io
import logging
from collections.abc import Generator
from contextlib import contextmanager

import polars as pl
from psycopg import Cursor

from src.config import settings
from src.infra.postgres import create_postgres_pool


logger = logging.getLogger(__name__)


def setup_staging_environment(cur: Cursor) -> None:
    cur.execute(f"SET LOCAL work_mem = '{settings.pg_trx_work_mem_mb}MB';")
    cur.execute(f"SET LOCAL temp_buffers = '{settings.pg_trx_temp_buffers_mb}MB';")
    cur.execute(f"SET LOCAL lock_timeout = '{settings.pg_trx_lock_timeout_sec}s';")
    cur.execute("SET jit = off;")
    cur.execute("SET synchronous_commit = off;")
    cur.execute("SELECT pg_advisory_xact_lock(12345);")

    cur.execute("""
        CREATE TEMP TABLE IF NOT EXISTS staging_transactions
        (LIKE transactions_risk_analysis INCLUDING DEFAULTS)
        ON COMMIT DROP;
    """)


@contextmanager
def pipeline_transaction_context() -> Generator[Cursor]:
    pool = create_postgres_pool()

    with (
        pool.connection() as conn,
        conn.transaction(),
        conn.cursor() as cur,
    ):
        yield cur


def upsert_transaction_batch(final_lf: pl.LazyFrame, cur: Cursor) -> int:
    final_df = final_lf.collect()
    df_height = final_df.height

    with io.BytesIO() as buffer:
        final_df.write_csv(buffer, include_header=False)
        del final_df

        with cur.copy("COPY staging_transactions FROM STDIN WITH (FORMAT CSV)") as copy:
            copy.write(buffer.getbuffer())

    cur.execute("ANALYZE staging_transactions;")

    cur.execute("""
        UPDATE staging_transactions s
        SET risk_score = s.risk_score + 75,
            score_reasons = s.score_reasons || '["payload_mutation_detected"]'::jsonb
        WHERE EXISTS (
            SELECT 1 FROM transactions_risk_analysis t
            WHERE t.transaction_id = s.transaction_id
                AND t.payload_hash != s.payload_hash
        );
    """)

    cur.execute("""
        INSERT INTO transactions_risk_analysis
        SELECT * FROM staging_transactions
        ON CONFLICT (transaction_id, payload_hash) DO NOTHING;
    """)

    cur.execute("TRUNCATE TABLE staging_transactions;")

    return df_height
