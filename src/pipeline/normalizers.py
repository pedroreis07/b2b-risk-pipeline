import hashlib
import io
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl
from psycopg import Connection
from psycopg_pool import ConnectionPool

from src.config import settings


HASH_FIELDS = (
    "transaction_id",
    "payer_cnpj",
    "receiver_cnpj",
    "amount",
    "invoice_id",
    "description",
)

LF_FIELDS = (
    "transaction_id",
    "payer_cnpj",
    "receiver_cnpj",
    "amount",
    "payer_status",
    "receiver_status",
    "payer_company_age",
    "receiver_company_age",
    "payer_capital_stock",
    "risk_score",
    "score_reasons",
    "payload_hash",
    "processed_at",
)


def extract_cnpjs(files: Path) -> set[str]:
    cnpjs = (
        pl.scan_parquet(files)
        .select(["payer_cnpj", "receiver_cnpj"])
        .unpivot()
        .select(cnpj=pl.col("value"))
        .unique()
        .drop_nulls()
        .collect()
        .get_column("cnpj")
        .to_list()
    )

    return set(cnpjs)


def add_score_columns(
    file: Path,
    payer_rf: pl.LazyFrame,
    receiver_rf: pl.LazyFrame,
    score_exprs: list[pl.Expr],
    reason_exprs: list[pl.Expr],
) -> pl.LazyFrame:
    file_lf = pl.scan_parquet(file)

    return (
        file_lf.join(payer_rf, left_on="payer_cnpj", right_on="cnpj", how="left")
        .join(receiver_rf, left_on="receiver_cnpj", right_on="cnpj", how="left")
        .with_columns(
            risk_score=pl.sum_horizontal(score_exprs),
            score_reasons=pl.format(
                "[{}]",
                pl.concat_list(reason_exprs)
                .list.drop_nulls()
                .list.eval(pl.format('"{}"', pl.element()))
                .list.join(","),
            ),
        )
    )


def _sha256_batch(s: pl.Series) -> pl.Series:
    return pl.Series([hashlib.sha256(x.encode("utf-8")).digest()[:16].hex() for x in s])


def add_hash_column(lf: pl.LazyFrame) -> pl.LazyFrame:
    concat_expr = pl.concat_str(HASH_FIELDS, separator="|")

    return lf.with_columns(
        payload_hash=concat_expr.map_batches(_sha256_batch, return_dtype=pl.String)
    )


def format_transaction_id(lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.with_columns(transaction_id=pl.col("transaction_id").str.slice(4))


def add_processed_date_column(lf: pl.LazyFrame) -> pl.LazyFrame:
    tz = ZoneInfo("America/Sao_Paulo")
    now = datetime.now(tz)
    return lf.with_columns(processed_at=pl.lit(now))


def reorder_columns(lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.select(LF_FIELDS)


def insert_lf_to_pg(
    lf: pl.LazyFrame,
    postgres_pool: ConnectionPool[Connection],
    file: Path,
    batch_id: uuid.UUID,
) -> int:
    tz = ZoneInfo("America/Sao_Paulo")
    start_date = datetime.now(tz)
    start_time = time.perf_counter()
    total_rows = 0

    with postgres_pool.connection() as conn, conn.transaction():
        conn.execute(
            """
                INSERT INTO pipeline_audit_log (batch_id, status, file, processed_at)
                VALUES (%s, 'PROCESSING', %s, %s);
                """,
            (batch_id, file.name, start_date),
        )

    lf = lf.sort(["transaction_id", "payload_hash"])

    try:
        with (
            postgres_pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            cur.execute(f"SET LOCAL work_mem = '{settings.pg_trx_work_mem_mb}MB';")  # type: ignore
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

            lf.sink_batches(
                write_batch,
                chunk_size=settings.batch_size,
                maintain_order=True,
            )  # type: ignore

            buf.close()

        end_time = time.perf_counter()
        duration = round(end_time - start_time, 2)
        with postgres_pool.connection() as conn, conn.transaction():
            conn.execute(
                """
                UPDATE pipeline_audit_log
                SET status = 'COMPLETED', total_rows = %s, duration_seconds = %s
                WHERE batch_id = %s;
                """,
                (total_rows, duration, batch_id),
            )
    except:
        end_time = time.perf_counter()
        duration = round(end_time - start_time, 2)
        with postgres_pool.connection() as conn, conn.transaction():
            conn.execute(
                """
                UPDATE pipeline_audit_log
                SET status = 'FAILED', duration_seconds = %s
                WHERE batch_id = %s;
                """,
                (duration, batch_id),
            )
        raise

    return total_rows
