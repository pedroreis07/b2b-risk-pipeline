import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

from src.config import SAO_PAULO_TZ
from src.pipeline import (
    enrich_and_score,
    extract_cnpjs,
    finalize_pipeline_columns,
    validate_file,
)
from src.services import (
    enrich_cnpjs,
    load_transactions_to_postgres,
    record_batch_completed,
    record_batch_failed,
    record_batch_start,
)


logger = logging.getLogger(__name__)


def process_file(file: Path) -> int:
    validate_file(file)

    batch_id = uuid.uuid4()
    started_at = datetime.now(tz=SAO_PAULO_TZ)
    start_time = time.perf_counter()

    record_batch_start(batch_id, file.name, started_at)

    try:
        cnpj_set = extract_cnpjs(file)
        cnpj_data = enrich_cnpjs(cnpj_set)

        lf = enrich_and_score(file, cnpj_data)
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
