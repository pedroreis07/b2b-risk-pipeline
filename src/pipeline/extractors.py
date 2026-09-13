from pathlib import Path

import polars as pl


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

    return set(cnpjs)
