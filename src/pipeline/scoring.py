from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

import polars as pl
import yaml

from src.config import settings


OPERATORS: dict[str, Callable] = {
    ">": pl.Expr.gt,
    "<": pl.Expr.lt,
    ">=": pl.Expr.ge,
    "<=": pl.Expr.le,
    "==": pl.Expr.eq,
    "!=": pl.Expr.ne,
}


@lru_cache(maxsize=1)
def load_rules(path: Path | None = None) -> tuple[list[pl.Expr], list[pl.Expr]]:
    path = path or settings.rules_path

    with path.open() as f:
        config = yaml.safe_load(f)

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
