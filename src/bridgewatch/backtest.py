"""Time-split backtests for Q1 (became Poor) and Q3 (became posted/restricted/closed).

A fold is (target, horizon h, test year T). The test set is every eligible bridge in year T, with outcomes in T+1..T+h.
Training uses base years T-h-TRAIN_YEARS+1 .. T-h, so every training label was already known by year T: no leakage.
Optional hold-out states are removed from training and scored separately (transfer to an agency the model never saw).
"""

import numpy as np
import polars as pl

from .db import connect
from .features import FEATURES
from .labels import LABELS, label_expr
from .paths import KEYED

TRAIN_YEARS = 8
TARGETS = {"poor": "became_poor", "restricted": "became_restricted"}


def load(years, h: int, target: str) -> pl.DataFrame:
    col = f"{TARGETS[target]}_{h}"
    ys = ",".join(str(y) for y in years)
    con = connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{KEYED}/nbi_*.parquet') WHERE year IN ({ys})")
    q = f"""
      SELECT f.*, y.{col} AS y FROM (
        SELECT p.bridge_id, p.year, {label_expr(h)}
        FROM p JOIN read_parquet('{LABELS}') l USING (bridge_id, year)) y
      JOIN read_parquet('{FEATURES}') f USING (bridge_id, year)
      WHERE y.{col} IS NOT NULL"""
    return con.execute(q).pl()


def fold(h: int, test_year: int, target: str, holdout_states=()):
    train_years = range(test_year - h - TRAIN_YEARS + 1, test_year - h + 1)
    train = load(train_years, h, target)
    test = load([test_year], h, target)
    if holdout_states:
        hs = list(holdout_states)
        train = train.filter(~pl.col("state_code").is_in(hs))
    return train, test


# ---------------------------------------------------------------- metrics

def brier(y, p) -> float:
    return float(np.mean((p - y) ** 2))


def auc(y, p) -> float:
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p))
    # average ranks for ties
    sp = p[order]
    i = 0
    while i < len(sp):
        j = i
        while j + 1 < len(sp) and sp[j + 1] == sp[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    pos = y == 1
    n1, n0 = pos.sum(), (~pos).sum()
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")


def average_precision(y, p) -> float:
    order = np.argsort(-p, kind="mergesort")
    ys = y[order]
    hits = np.cumsum(ys)
    prec = hits / np.arange(1, len(ys) + 1)
    return float((prec * ys).sum() / max(ys.sum(), 1))


def precision_at(y, p, frac: float) -> float:
    k = max(1, round(frac * len(p)))
    top = np.argsort(-p, kind="mergesort")[:k]
    return float(y[top].mean())


def reliability(y, p, bins: int = 10):
    """Equal-count bins: mean predicted vs observed rate."""
    order = np.argsort(p, kind="mergesort")
    out = []
    for chunk in np.array_split(order, bins):
        if len(chunk):
            out.append((float(p[chunk].mean()), float(y[chunk].mean()), len(chunk)))
    return out


def score(y, p, base_rate: float) -> dict:
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    b, bref = brier(y, p), brier(y, np.full_like(p, base_rate))
    return {"n": len(y), "events": int(y.sum()), "rate": float(y.mean()), "brier": b, "brier_skill": 1 - b / bref,
            "auc": auc(y, p), "avg_precision": average_precision(y, p), "precision_top1pct": precision_at(y, p, 0.01),
            "precision_top5pct": precision_at(y, p, 0.05), "reliability": reliability(y, p)}
