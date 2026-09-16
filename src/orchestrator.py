import logging
import time
from datetime import datetime
from pathlib import Path

import polars as pl
import pyarrow.parquet as pq
import uuid_utils as uuid

from src import SAO_PAULO_TZ, settings
from src.infra import sort_large_parquet
from src.pipeline import (
    apply_risk_scoring,
    extract_unique_cnpjs,
    finalize_pipeline_columns,
    load_cnpjs_as_lazyframe,
    validate_file,
)
from src.repositories import (
    pipeline_transaction_context,
    record_batch_completed,
    record_batch_failed,
    record_batch_start,
    setup_staging_environment,
    upsert_transaction_batch,
)
from src.services import fetch_cnpj_data_batch


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
        sorted_file = settings.sorted_dir / file.name
        sorted_file.parent.mkdir(parents=True, exist_ok=True)
        sort_large_parquet(file, sorted_file)

        parquet_file = pq.ParquetFile(sorted_file)

        total_rows = 0
        logger.info(
            "Starting database load process (batch_size=%d)", settings.batch_size
        )

        with pipeline_transaction_context() as cur:
            is_first_batch = True

            for batch in parquet_file.iter_batches(batch_size=settings.batch_size):
                raw_lf = pl.from_arrow(batch).lazy()
                del batch

                cnpj_set = extract_unique_cnpjs(raw_lf.collect())

                enriched_cnpjs = fetch_cnpj_data_batch(cnpj_set)
                del cnpj_set

                cnpj_data_lf = load_cnpjs_as_lazyframe(enriched_cnpjs)
                del enriched_cnpjs

                cnpj_data_df_w_risk = apply_risk_scoring(raw_lf, cnpj_data_lf)
                del raw_lf

                final_lf = finalize_pipeline_columns(cnpj_data_df_w_risk)

                if is_first_batch:
                    setup_staging_environment(cur)
                    is_first_batch = False

                df_height = upsert_transaction_batch(final_lf, cur)

                total_rows += df_height

                logger.debug(
                    "Loaded batch: %d rows (cumulative: %d)",
                    df_height,
                    total_rows,
                )

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
