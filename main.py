import logging
from pathlib import Path

from src.config import settings
from src.db import create_postgres_pool, create_redis_client, ensure_schema
from src.process import process_files


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

redis_client = create_redis_client()
postgres_pool = create_postgres_pool()


def main():
    folder = Path(settings.data_dir)
    files = list(folder.glob("*.parquet"))

    if not files:
        logger.warning("No files were found in %s", folder)
        return

    ensure_schema(postgres_pool)

    for file in files:
        process_files(file, redis_client, postgres_pool)


if __name__ == "__main__":
    main()
