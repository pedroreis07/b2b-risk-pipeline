import logging
from pathlib import Path

import polars as pl


logger = logging.getLogger(__name__)


def extract_cnpjs(file: Path) -> set[str]:
    cnpjs = (
        pl.scan_parquet(file)
        .select(["payer_cnpj", "receiver_cnpj"])
        .unpivot()
        .select(cnpj=pl.col("value"))
        .unique()
        .drop_nulls()
        .collect()
        .get_column("cnpj")
        .to_list()
    )

    cnpj_set = set(cnpjs)
    logger.info("Extracted %d unique CNPJs from %s", len(cnpj_set), file.name)
    return cnpj_set
