from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl


HASH_FIELDS = (
    "transaction_id",
    "payer_cnpj",
    "receiver_cnpj",
    "amount",
    "invoice_id",
    "description",
)

LF_FIELDS = (
    "transaction_id",
    "payer_cnpj",
    "receiver_cnpj",
    "amount",
    "payer_status",
    "receiver_status",
    "payer_company_age",
    "receiver_company_age",
    "payer_capital_stock",
    "risk_score",
    "score_reasons",
    "payload_hash",
    "processed_at",
)


def extract_cnpjs(files: Path) -> set[str]:
    cnpjs = (
        pl.scan_parquet(files)
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


def add_score_columns(
    file: Path,
    payer_rf: pl.LazyFrame,
    receiver_rf: pl.LazyFrame,
    score_exprs: list[pl.Expr],
    reason_exprs: list[pl.Expr],
) -> pl.LazyFrame:
    file_lf = pl.scan_parquet(file)

    return (
        file_lf.join(payer_rf, left_on="payer_cnpj", right_on="cnpj", how="left")
        .join(receiver_rf, left_on="receiver_cnpj", right_on="cnpj", how="left")
        .with_columns(
            risk_score=pl.sum_horizontal(score_exprs),
            score_reasons=pl.format(
                "[{}]",
                pl.concat_list(reason_exprs)
                .list.drop_nulls()
                .list.eval(pl.format('"{}"', pl.element()))
                .list.join(","),
            ),
        )
    )


def add_hash_column(lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.with_columns(payload_hash=pl.struct(HASH_FIELDS).hash(seed=42))


def add_processed_date_column(lf: pl.LazyFrame) -> pl.LazyFrame:
    tz = ZoneInfo("America/Sao_Paulo")
    now = datetime.now(tz)
    return lf.with_columns(processed_at=pl.lit(now))


def reorder_columns(lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.select(LF_FIELDS)


def write_results(lf: pl.LazyFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lf.sink_parquet(output_path)

