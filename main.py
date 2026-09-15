import logging

from src.config import settings
from src.infra import (
    create_http_manager,
    create_postgres_pool,
    create_redis_client,
    ensure_schema,
)
from src.orchestrator import process_file


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    folder = settings.data_dir
    files = sorted(folder.glob("*.parquet"))

    if not files:
        logger.warning("No files were found in %s", folder)
        return

    logger.info("Found %d parquet file(s) in %s", len(files), folder)

    create_redis_client()
    create_postgres_pool()
    create_http_manager()

    logger.info("Infrastructure initialized (Redis + PostgreSQL + HTTP)")

    ensure_schema()

    for file in files:
        process_file(file)

    logger.info("All files processed successfully")


if __name__ == "__main__":
    main()
