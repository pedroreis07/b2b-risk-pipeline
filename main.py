import logging
from pathlib import Path

from src.config import settings
from src.db import create_redis_client
from src.process import process_files


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

redis_client = create_redis_client()


def main():
    folder = Path(settings.data_dir)
    files = list(folder.glob("*.parquet"))

    if not files:
        logger.warning("No files were found in %s", folder)
        return

    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        output_path = output_dir / file.name
        process_files(file, output_path, redis_client)


if __name__ == "__main__":
    main()
