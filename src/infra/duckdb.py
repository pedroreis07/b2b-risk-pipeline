import logging
from pathlib import Path

import duckdb

from src.config import settings


logger = logging.getLogger(__name__)


def sort_large_parquet(input_file: Path, output_file: Path) -> None:
    logger.info("Starting sorting for %s", input_file.name)

    con = duckdb.connect()

    temp_dir = output_file.parent.absolute()
    con.execute(
        "PRAGMA memory_limit=$memory_limit;",
        {"memory_limit": f"{settings.duck_db_memory_limit_mb}MB"},
    )
    con.execute(
        "PRAGMA temp_directory=$temp_directory;",
        {"temp_directory": str(temp_dir)},
    )

    con.execute(
        """
        COPY (
            SELECT * FROM read_parquet($input_path)
            ORDER BY transaction_id ASC
        ) TO $output_path (FORMAT PARQUET);
        """,
        {"input_path": str(input_file), "output_path": str(output_file)},
    )

    con.close()
    logger.info("Sorting complete. Sorted file saved to %s", output_file.name)
