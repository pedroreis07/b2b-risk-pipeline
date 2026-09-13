import hashlib
import logging
from datetime import datetime

import polars as pl

from src.config import SAO_PAULO_TZ


logger = logging.getLogger(__name__)


HASH_FIELDS = (
    "transaction_id",
    "payer_cnpj",
    "receiver_cnpj",
    "amount",
    "invoice_id",
    "description",
)

FINAL_COLUMNS = (
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


def sha256_batch(s: pl.Series) -> pl.Series:
    return pl.Series(
        [
            hashlib.sha256(x.encode("utf-8"), usedforsecurity=False).digest()[:16].hex()
            for x in s
        ]
    )


def format_transaction_id(lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.with_columns(transaction_id=pl.col("transaction_id").str.slice(4))


def add_hash_column(lf: pl.LazyFrame) -> pl.LazyFrame:
    concat_expr = pl.concat_str(HASH_FIELDS, separator="|")
    return lf.with_columns(
        payload_hash=concat_expr.map_batches(sha256_batch, return_dtype=pl.String)
    )


def add_processed_date_column(lf: pl.LazyFrame) -> pl.LazyFrame:
    now = datetime.now(tz=SAO_PAULO_TZ)
    return lf.with_columns(processed_at=pl.lit(now))


def reorder_columns(lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.select(FINAL_COLUMNS)


def finalize_pipeline_columns(lf: pl.LazyFrame) -> pl.LazyFrame:
    logger.debug("Finalizing pipeline columns (hash + transaction_id + processed_at)")
    lf = format_transaction_id(lf)
    lf = add_hash_column(lf)
    lf = add_processed_date_column(lf)
    return reorder_columns(lf)
