import logging
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

import polars as pl
import yaml

from src.config import settings


logger = logging.getLogger(__name__)


OPERATORS: dict[str, Callable] = {
    ">": pl.Expr.gt,
    "<": pl.Expr.lt,
    ">=": pl.Expr.ge,
    "<=": pl.Expr.le,
    "==": pl.Expr.eq,
    "!=": pl.Expr.ne,
}

CNPJ_CACHE_SCHEMA = {
    "cnpj": pl.String,
    "status": pl.String,
    "company_age": pl.Float64,
    "capital_stock": pl.Float64,
}


@lru_cache(maxsize=1)
def load_rules() -> tuple[list[pl.Expr], list[pl.Expr]]:
    path = settings.rules_path

    with path.open() as f:
        config = yaml.safe_load(f)

    logger.info("Loaded %d risk rules from %s", len(config["rules"]), path)

    score_exprs = []
    reason_exprs = []

    for rule in config["rules"]:
        op_fn = OPERATORS.get(rule["operator"])

        if op_fn is None:
            raise ValueError(f"Unsupported operator: {rule['operator']}")

        left = pl.col(rule["column"])

        if "compare_column" in rule:
            condition = op_fn(left, pl.col(rule["compare_column"]))
        else:
            condition = op_fn(left, rule["value"])

        score_exprs.append(pl.when(condition).then(rule["points"]).otherwise(0))
        reason_exprs.append(pl.when(condition).then(pl.lit(rule["reason"])))

    return score_exprs, reason_exprs


def apply_risk_scoring(
    file: Path,
    cnpj_data: dict[str, dict],
) -> pl.LazyFrame:
    score_exprs, reason_exprs = load_rules()

    file_lf = pl.scan_parquet(file)
    rf_cache_lf = pl.from_dicts(
        list(cnpj_data.values()), schema=CNPJ_CACHE_SCHEMA
    ).lazy()

    payer_lf = rf_cache_lf.rename(
        {
            "status": "payer_status",
            "company_age": "payer_company_age",
            "capital_stock": "payer_capital_stock",
        }
    )
    receiver_lf = rf_cache_lf.rename(
        {
            "status": "receiver_status",
            "company_age": "receiver_company_age",
        }
    ).drop("capital_stock")

    logger.debug("Applying %d risk rules to %s", len(score_exprs), file.name)

    return (
        file_lf.join(payer_lf, left_on="payer_cnpj", right_on="cnpj", how="left")
        .join(receiver_lf, left_on="receiver_cnpj", right_on="cnpj", how="left")
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
