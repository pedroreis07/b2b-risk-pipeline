import logging
from collections.abc import Callable
from functools import lru_cache

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
    chunk_lf: pl.LazyFrame,
    cnpj_data_lf: pl.LazyFrame,
) -> pl.LazyFrame:
    score_exprs, reason_exprs = load_rules()

    payer_lf = cnpj_data_lf.rename(
        {
            "cnpj": "payer_cnpj",
            "status": "payer_status",
            "company_age": "payer_company_age",
            "capital_stock": "payer_capital_stock",
        }
    )
    receiver_lf = cnpj_data_lf.rename(
        {
            "cnpj": "receiver_cnpj",
            "status": "receiver_status",
            "company_age": "receiver_company_age",
        }
    ).drop("capital_stock")

    logger.debug("Applying risk rules")

    return (
        chunk_lf.join(payer_lf, on="payer_cnpj", how="left")
        .join(receiver_lf, on="receiver_cnpj", how="left")
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
