"""Q2: with a budget, which bridges should be treated first? Plus closure candidates.

For each open bridge in the decision year:
  risk          P(posted, restricted or closed within h years), from the Q3 model
  consequence   detour user cost per day if it is restricted (costs.detour_cost_per_day), floored at $1/day; NBI "no detour"
                codes (>= 150 km) are costed as a 100 km detour (assumption)
  action/cost   rehabilitation (68% of FHWA replacement cost) for Fair/Good bridges, replacement for Poor ones; deck
                area = length x width, or length x 7.3 m where NBI codes width 0 (culverts), at least 20 m²
  value         risk x consequence x 365 x h: expected user cost avoided over the horizon if treatment prevents the event

Strategies spend the same budget, taking bridges in their own order until the money runs out:
  worst_first   lowest condition rating first, then higher traffic (common practice)
  traffic_first highest ADT first
  risk_first    highest model risk first (ignores cost and consequence)
  value_per_$   highest value / cost first (greedy knapsack)
  value_per_$ with baseline risk (backtest only): the same rule with time-in-condition risk instead of the model, to show
                how much of the gain comes from the model and how much from weighting by consequence and cost

Backtest: decide with year-T data, then count from what really happened in T+1..T+h how many restricted/closed events, and
how much detour exposure (vehicles/day x detour km), fell inside each strategy's treated set. This measures targeting: we
cannot observe whether a treatment would have prevented the event.

Closure candidates: open bridges where keeping the crossing costs more than the detour would, i.e. the replacement cost
exceeds 20 years of detour user cost (undiscounted, a deliberately conservative screen). Listed, never auto-selected.
"""

import json

import numpy as np
import polars as pl

from . import backtest, costs
from .baselines import TimeInCondition
from .db import connect
from .model import GBM
from .paths import KEYED, REPORTS

STRATEGIES = ("worst_first", "traffic_first", "risk_first", "value_per_dollar")
BACKTEST_STRATEGIES = (*STRATEGIES, "value_per_dollar_baseline_risk")


ROADWAY_M = 7.3  # assumed roadway width where NBI codes deck width 0 (culverts under fill); FHWA uses approach width there
MIN_AREA_M2 = 20.0
NO_DETOUR_CODE_KM = 150.0  # NBI item 19: 199 km / 999 = no detour; 158-161 km = the old "99 miles" code converted
NO_DETOUR_KM = 100.0  # assumption: a closure with no detour route is costed as a 100 km detour


def detour_length(df: pl.DataFrame) -> np.ndarray:
    """Detour km for costing. Uses the raw NBI value when present, so "no detour" codes are not mistaken for 0."""
    raw = df["detour_raw"] if "detour_raw" in df.columns else df["detour_km"]
    d = raw.fill_null(0).to_numpy().astype(float)
    return np.where(d >= NO_DETOUR_CODE_KM, NO_DETOUR_KM, d)


def deck_area(df: pl.DataFrame) -> np.ndarray:
    """Deck area for costing: length x deck width; where width is 0 (mostly culverts), length x an assumed roadway width."""
    if "length_m" in df.columns:
        length = df["length_m"].fill_null(0).to_numpy()
        width = df["deck_width_m"].fill_null(0).to_numpy()
        area = np.where(width > 0, length * width, length * ROADWAY_M)
    else:
        area = np.expm1(df["log_deck_area"].fill_null(0).to_numpy())
    return np.maximum(area, MIN_AREA_M2)


def frame(df: pl.DataFrame, risk: np.ndarray, h: int, uc: dict) -> pl.DataFrame:
    nhs = (df["nhs"] == "1").to_list()
    area = deck_area(df)
    st = df["state_code"].to_list()
    repl = np.array([costs.replacement_cost(s, n, a, uc) for s, n, a in zip(st, nhs, area, strict=True)])
    poor = (df["lowest_rating"].fill_null(9) <= 4).to_numpy()
    cost = np.where(poor, repl, costs.REHAB_SHARE * repl)
    adt = np.expm1(df["log_adt"].fill_null(0).to_numpy())
    detour = detour_length(df)
    truck = df["truck_pct"].fill_null(0).to_numpy()
    per_day = np.array([costs.detour_cost_per_day(a, d, t) for a, d, t in zip(adt, detour, truck, strict=True)])
    per_day = np.maximum(per_day, 1.0)
    return df.select("bridge_id", "state_code", "lowest_rating").with_columns(
        pl.Series("risk", risk), pl.Series("cost", cost), pl.Series("replacement", repl),
        pl.Series("adt", adt), pl.Series("detour_km", detour), pl.Series("detour_cost_day", per_day),
        pl.Series("exposure", adt * detour), pl.Series("value", risk * per_day * 365 * h))


def order(f: pl.DataFrame, strategy: str) -> np.ndarray:
    if strategy == "worst_first":
        return np.lexsort((-f["adt"].to_numpy(), f["lowest_rating"].fill_null(9).to_numpy()))
    if strategy == "traffic_first":
        return np.argsort(-f["adt"].to_numpy(), kind="mergesort")
    if strategy == "risk_first":
        return np.argsort(-f["risk"].to_numpy(), kind="mergesort")
    return np.argsort(-(f["value"].to_numpy() / f["cost"].to_numpy()), kind="mergesort")


def pick(f: pl.DataFrame, strategy: str, budget: float) -> np.ndarray:
    """Walk the strategy's order and fund every bridge that still fits; skip (do not stop at) one that does not."""
    cost = f["cost"].to_numpy()
    chosen, spent = np.zeros(f.height, bool), 0.0
    for i in order(f, strategy):
        if spent + cost[i] <= budget:
            chosen[i], spent = True, spent + cost[i]
    return chosen


def closure_candidates(f: pl.DataFrame, years: int = 20) -> pl.DataFrame:
    return f.filter(pl.col("replacement") > pl.col("detour_cost_day") * 365 * years).sort("detour_cost_day")


def backtest_plan(decision_year: int = 2017, h: int = 4, budgets=(1e8, 5e8, 1e9, 5e9), states=None) -> dict:
    train, test = backtest.fold(h, decision_year, "restricted")
    con = connect()
    dims = con.execute(f"""SELECT bridge_id, length_m, deck_width_m, detour_km AS detour_raw
                           FROM read_parquet('{KEYED}/nbi_{decision_year}.parquet')""").pl()
    test = test.join(dims, on="bridge_id", how="left")
    if states:
        test = test.filter(pl.col("state_code").is_in(list(states)))
    model = GBM(name="q3").fit(train)
    uc = costs.unit_costs()
    f = frame(test, model.predict(test), h, uc).with_columns(test["y"].cast(pl.Float64).alias("event"))
    fb = frame(test, TimeInCondition().fit(train).predict(test), h, uc)
    ev, ex = f["event"].to_numpy(), f["exposure"].to_numpy()
    out = {"decision_year": decision_year, "h": h, "bridges": f.height, "events": int(ev.sum()),
           "event_exposure": float((ev * ex).sum()), "total_cost_all": float(f["cost"].sum()), "results": []}
    for b in budgets:
        for s in BACKTEST_STRATEGIES:
            c = pick(fb, "value_per_dollar", b) if s == "value_per_dollar_baseline_risk" else pick(f, s, b)
            out["results"].append({"budget": b, "strategy": s, "treated": int(c.sum()), "events_covered": int(ev[c].sum()),
                                   "exposure_covered": float((ev * ex)[c].sum()), "spent": float(f["cost"].to_numpy()[c].sum())})
    out["closure_candidates"] = closure_candidates(f).height
    return out


def run_plan() -> dict:
    out = backtest_plan()
    (REPORTS / "plan.json").write_text(json.dumps(out, indent=1))
    for r in out["results"]:
        print(f"budget ${r['budget'] / 1e6:,.0f}M {r['strategy']:16s} treated {r['treated']:6,} events {r['events_covered']:5,} "
              f"exposure {r['exposure_covered'] / max(out['event_exposure'], 1):.1%}", flush=True)
    return out
