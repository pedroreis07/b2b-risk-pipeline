import logging
from pathlib import Path

import polars as pl


logger = logging.getLogger(__name__)


def validate_file(file: Path) -> None:
    logger.info("Validating file: %s", file.name)
    lf = pl.scan_parquet(file)
    null_counts = lf.select(pl.all().null_count()).collect().row(0, named=True)

    cols_with_nulls = {col: count for col, count in null_counts.items() if count > 0}
    if cols_with_nulls:
        logger.error("Validation failed for %s: %s", file.name, cols_with_nulls)
        raise ValueError(f"{file.name}: columns with null values: {cols_with_nulls}")
    logger.info("Validation passed for %s", file.name)
