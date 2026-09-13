import io
import logging

import polars as pl

from src.config import settings
from src.infra import create_postgres_pool


logger = logging.getLogger(__name__)


def load_transactions_to_postgres(lf: pl.LazyFrame) -> int:
    logger.info("Starting database load (batch_size=%d)", settings.batch_size)
    pool = create_postgres_pool()
    total_rows = 0
    sorted_lf = lf.sort(["transaction_id", "payload_hash"])

    with (
        pool.connection() as conn,
        conn.transaction(),
        conn.cursor() as cur,
    ):
        cur.execute(f"SET LOCAL work_mem = '{settings.pg_trx_work_mem_mb}MB';")
        cur.execute("""
            CREATE TEMP TABLE staging_transactions
            (LIKE transactions_risk_analysis INCLUDING DEFAULTS)
            ON COMMIT DROP;
        """)

        buf = io.BytesIO()

        def write_batch(batch_df: pl.DataFrame) -> None:
            nonlocal total_rows
            buf.seek(0)
            buf.truncate(0)
            batch_df.write_csv(buf, include_header=False)

            with cur.copy(
                "COPY staging_transactions FROM STDIN WITH (FORMAT CSV)"
            ) as copy:
                copy.write(buf.getbuffer())

            cur.execute("""
                INSERT INTO transactions_risk_analysis
                SELECT * FROM staging_transactions
                ON CONFLICT (transaction_id, payload_hash) DO NOTHING;
            """)
            cur.execute("TRUNCATE staging_transactions;")
            total_rows += batch_df.height
            logger.debug(
                "Loaded batch: %d rows (cumulative: %d)", batch_df.height, total_rows
            )

        sorted_lf.sink_batches(
            write_batch,
            chunk_size=settings.batch_size,
            maintain_order=True,
        )

        buf.close()

    logger.info("Database load complete: %d total rows", total_rows)
    return total_rows
