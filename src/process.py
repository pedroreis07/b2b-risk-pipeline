import logging
from pathlib import Path

import polars as pl
from psycopg import Connection
from psycopg_pool import ConnectionPool
from redis import Redis

from src.pipeline.transforms import (
    add_hash_column,
    add_processed_date_column,
    add_score_columns,
    extract_cnpjs,
    insert_lf_to_pg,
    reorder_columns,
)
from src.pipeline.validators import validate_file
from src.rules.engine import load_rules
from src.services.cnpj import enrich_cnpjs


logger = logging.getLogger(__name__)


def process_files(
    file: Path,
    redis_client: Redis,
    postgres_pool: ConnectionPool[Connection],
) -> None:
    validate_file(file)

    cnpj_set = extract_cnpjs(file)
    cnpj_data = enrich_cnpjs(cnpj_set, redis_client)
    rf_cache_lf = pl.from_dicts(list(cnpj_data.values())).lazy()
    payer_lf = rf_cache_lf.rename(
        {
            "status": "payer_status",
            "company_age": "payer_company_age",
            "capital_stock": "payer_capital_stock",
        }
    )
    receiver_lf = rf_cache_lf.rename(
        {
            "status": "receiver_status",
            "company_age": "receiver_company_age",
        }
    ).drop("capital_stock")
    score_exprs, reason_exprs = load_rules()

    lf = add_score_columns(
        file,
        payer_lf,
        receiver_lf,
        score_exprs,
        reason_exprs,
    )
    lf = add_hash_column(lf)
    lf = add_processed_date_column(lf)
    lf = reorder_columns(lf)
    rows_inserted = insert_lf_to_pg(lf, postgres_pool)

    logger.info(
        "Processed %s -> database (%d rows)",
        file.name,
        rows_inserted,
    )
