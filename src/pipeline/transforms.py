import logging
from datetime import datetime

import polars as pl
import polars_hash as plh

from src import SAO_PAULO_TZ


logger = logging.getLogger(__name__)

CNPJ_DATA_LF_SCHEMA = {
    "cnpj": pl.String,
    "status": pl.Categorical,
    "activity_start_date": pl.String,
    "capital_stock": pl.Float32,
}

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


def add_company_age_column(lf: pl.LazyFrame) -> pl.LazyFrame:
    now = datetime.now(tz=SAO_PAULO_TZ).date()

    date_col = pl.col("activity_start_date").str.to_date("%Y-%m-%d")
    age_expr = (
        ((pl.lit(now) - date_col).dt.total_days() / 365.25).cast(pl.Float32).round(1)
    )

    return lf.with_columns(company_age=age_expr).drop("activity_start_date")


def load_cnpjs_as_lazyframe(cnpj_data: dict[str, dict]) -> pl.LazyFrame:
    lf = pl.from_dicts(list(cnpj_data.values()), schema=CNPJ_DATA_LF_SCHEMA).lazy()
    return add_company_age_column(lf)


def extract_unique_cnpjs(df: pl.DataFrame) -> set[str]:
    return set(pl.concat([df["payer_cnpj"], df["receiver_cnpj"]]).unique())


def format_transaction_id(lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.with_columns(transaction_id=pl.col("transaction_id").str.slice(4))


def add_hash_column(lf: pl.LazyFrame) -> pl.LazyFrame:
    concat_expr = plh.concat_str(HASH_FIELDS, separator="|")
    return lf.with_columns(payload_hash=concat_expr.chash.sha2_256().str.slice(0, 32))


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
