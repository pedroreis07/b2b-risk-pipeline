import logging
from pathlib import Path

import pyarrow.parquet as pq


logger = logging.getLogger(__name__)


def validate_file(file: Path) -> None:
    logger.info("Validating file metadata: %s", file.name)
    parquet_file = pq.ParquetFile(file)
    metadata = parquet_file.metadata

    for rg_idx in range(metadata.num_row_groups):
        row_group = metadata.row_group(rg_idx)

        for col_idx in range(metadata.num_columns):
            col_meta = row_group.column(col_idx)

            if col_meta.statistics and col_meta.statistics.null_count > 0:
                logger.error("Validation failed for %s: found null values", file.name)
                raise ValueError(f"{file.name}: file contains null values.")

    logger.info("Validation passed for %s", file.name)
