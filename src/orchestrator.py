import logging
import time
from datetime import datetime
from pathlib import Path

import polars as pl
import uuid_utils as uuid

from src.config import SAO_PAULO_TZ
from src.pipeline import (
    apply_risk_scoring,
    extract_unique_cnpjs,
    finalize_pipeline_columns,
    load_cnpjs_as_lazyframe,
    validate_file,
)
from src.services import (
    fetch_cnpj_data_batch,
    load_transactions_to_postgres,
    record_batch_completed,
    record_batch_failed,
    record_batch_start,
)


logger = logging.getLogger(__name__)


def process_file(file: Path) -> int:
    validate_file(file)

    started_at = datetime.now(tz=SAO_PAULO_TZ)
    ns = int(started_at.timestamp() * 10**9)
    batch_id: uuid.UUID = uuid.uuid7(nanoseconds=ns).hex
    start_time = time.perf_counter()

    logger.info("Starting pipeline for %s (batch_id=%s)", file.name, batch_id)
    record_batch_start(batch_id, file.name, started_at)

    try:
        raw_lf = pl.scan_parquet(file)
        cnpj_set = extract_unique_cnpjs(raw_lf.collect())
        enriched_cnpjs = fetch_cnpj_data_batch(cnpj_set)
        cnpj_data_lf = load_cnpjs_as_lazyframe(enriched_cnpjs)

        lf = apply_risk_scoring(raw_lf, cnpj_data_lf)
        lf = finalize_pipeline_columns(lf)

        total_rows = load_transactions_to_postgres(lf)

        duration = round(time.perf_counter() - start_time, 2)
        finished_at = datetime.now(tz=SAO_PAULO_TZ)
        record_batch_completed(batch_id, total_rows, duration, finished_at)

        logger.info(
            "Processed %s -> database (%d rows in %.2fs)",
            file.name,
            total_rows,
            duration,
        )
        return total_rows

    except Exception:
        duration = round(time.perf_counter() - start_time, 2)
        finished_at = datetime.now(tz=SAO_PAULO_TZ)
        record_batch_failed(batch_id, duration, finished_at)
        logger.exception("Failed to process file %s after %.2fs", file.name, duration)
        raise
