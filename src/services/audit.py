import logging
import uuid
from datetime import datetime

from src.infra import create_postgres_pool


logger = logging.getLogger(__name__)


def record_batch_start(
    batch_id: uuid.UUID,
    file_name: str,
    started_at: datetime,
) -> None:
    pool = create_postgres_pool()
    with pool.connection() as conn, conn.transaction():
        conn.execute(
            """
            INSERT INTO pipeline_audit_log (batch_id, status, file, started_at)
            VALUES (%s, 'PROCESSING', %s, %s);
            """,
            (batch_id, file_name, started_at),
        )
    logger.debug("Audit: batch %s marked PROCESSING (file=%s)", batch_id, file_name)


def record_batch_completed(
    batch_id: uuid.UUID,
    total_rows: int,
    duration_seconds: float,
    finished_at: datetime,
) -> None:
    pool = create_postgres_pool()
    with pool.connection() as conn, conn.transaction():
        conn.execute(
            """
            UPDATE pipeline_audit_log
            SET status = 'COMPLETED', total_rows = %s, duration_seconds = %s, finished_at = %s
            WHERE batch_id = %s;
            """,
            (total_rows, duration_seconds, finished_at, batch_id),
        )
    logger.debug("Audit: batch %s marked COMPLETED (%d rows, %.2fs)", batch_id, total_rows, duration_seconds)


def record_batch_failed(
    batch_id: uuid.UUID,
    duration_seconds: float,
    finished_at: datetime,
) -> None:
    pool = create_postgres_pool()
    with pool.connection() as conn, conn.transaction():
        conn.execute(
            """
            UPDATE pipeline_audit_log
            SET status = 'FAILED', duration_seconds = %s, finished_at = %s
            WHERE batch_id = %s;
            """,
            (duration_seconds, finished_at, batch_id),
        )
    logger.warning("Audit: batch %s marked FAILED (%.2fs)", batch_id, duration_seconds)
