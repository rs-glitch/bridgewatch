"""Score the latest NBI year (2025) for the platform: Q1, Q3 and Q4 risks plus Q2 planning fields for every bridge.

Models are trained on the most recent base years whose 4-year outcomes are fully observed (2014-2021 -> outcomes to 2025),
then applied to 2025 records. Output: data/scores_2025.parquet, one row per bridge.
"""

import numpy as np
import polars as pl

from . import backtest, costs, planner, screen
from .db import connect
from .features import FEATURES
from .model import GBM
from .paths import DATA, KEYED

H = 4
SCORES = DATA / "scores_{year}.parquet"


def latest_features(year: int) -> pl.DataFrame:
    con = connect()
    return con.execute(f"""
      SELECT f.*, p.nbi_id, p.county_code, p.year_built, p.adt, p.length_m, p.deck_width_m,
             p.detour_km AS detour_raw, p.carries, p.crosses, p.location_desc,
             p.posting_status AS posting, p.condition,
             p.inspection_interval_mo AS interval, {screen.method1_expr()} AS method1
      FROM read_parquet('{FEATURES}') f JOIN read_parquet('{KEYED}/nbi_{year}.parquet') p USING (bridge_id, year)
      WHERE f.year = {year}""").pl()


def score(year: int = 2025) -> pl.DataFrame:
    train_years = range(year - H - backtest.TRAIN_YEARS + 1, year - H + 1)
    cur = latest_features(year)
    poor = GBM(name="q1").fit(backtest.load(train_years, H, "poor"))
    restr = GBM(name="q3").fit(backtest.load(train_years, H, "restricted"))
    q4 = GBM(name="q4").fit(screen.load(train_years))
    p_poor = np.where(cur["condition"] == "Poor", np.nan, poor.predict(cur))
    p_restr = np.where(cur["posting"] == "A", restr.predict(cur), np.nan)
    p_miss = q4.predict(cur)
    plan = planner.frame(cur, np.nan_to_num(p_restr, nan=0.0), H, costs.unit_costs())
    out = cur.select("bridge_id", "nbi_id", "state_code", "county_code", "carries", "crosses", "location_desc", "lat", "lon",
                     "year_built", "adt", "condition",
                     "lowest_rating", "deck", "superstructure", "substructure", "culvert", "posting", "interval", "method1",
                     "owner", "material", "design_type", "nhs").with_columns(
        pl.Series("p_poor_4y", p_poor), pl.Series("p_restricted_4y", p_restr), pl.Series("p_q4_miss_4y", p_miss),
        plan["cost"].alias("treatment_cost"), plan["replacement"].alias("replacement_cost"),
        plan["detour_cost_day"].alias("detour_cost_day"), plan["value"].alias("value_4y"),
        (cur["detour_raw"].fill_null(0) >= planner.NO_DETOUR_CODE_KM).alias("no_detour"))
    out = out.with_columns((pl.col("value_4y") / pl.col("treatment_cost")).alias("value_per_dollar"))
    out.write_parquet(str(SCORES).format(year=year))
    return out
