"""Q4: inspection-interval screen. Which bridges on a 24-month cycle look low-risk enough for 48 months, and how often would
that have gone wrong?

A "miss" is any of these within the 4 years after the base year: the bridge became Poor, was posted/restricted/closed, or a
component rating fell by 2 or more points. Bridges whose record ends before 4 years without a miss are excluded (unknown).

Compared, on the same base year:
  method1   our encoding of the 23 CFR 650.311 Method 1 criteria for extended (48-month) intervals:
            deck, superstructure, substructure (or culvert) all >= 6; channel >= 6 or not over water; inventory rating >=
            HS-20 (32.4 t); scour stable (item 113 in 4, 5, 7, 8, 9 or N); concrete or steel; slab, girder/beam, deck arch or
            culvert; roadway vertical clearances >= 14 ft (4.27 m) over and, for a highway underneath, under.
  model     the same number of bridges, picked by lowest predicted miss risk (a gradient-boosted model trained only on base
            years whose 4-year outcomes were known by the base year)
  hybrid    the method1-eligible bridges minus the riskiest 10% of them by model score

This is evidence for an agency's own Method 1/Method 2 policy. Interval decisions belong to the bridge owner.
"""

import json

import numpy as np
import polars as pl

from .db import connect
from .features import FEATURES
from .labels import LABELS, q4_miss_expr
from .model import GBM
from .paths import KEYED, REPORTS

HS20_T = 32.35  # HS-20 = 36 short tons = 32.4 metric tons; NBI stores one decimal
CLEAR_M = 4.27  # 14 ft
STABLE_SCOUR = ("4", "5", "7", "8", "9", "N")
TYPES = ("01", "02", "03", "04", "05", "06", "11", "19")  # slab, beam/girder families, deck arch, culvert
MATERIALS = ("1", "2", "3", "4", "5", "6")  # concrete, steel, prestressed concrete (simple or continuous)


def method1_expr() -> str:
    comps = " AND ".join(f"coalesce(p.{c}, 9) >= 6" for c in ("deck", "superstructure", "substructure", "culvert"))
    return f"""({comps}
      AND coalesce(try_cast(p.channel AS INTEGER), 9) >= 6
      AND p.inventory_rating_t >= {HS20_T}
      AND p.scour_code IN {STABLE_SCOUR}
      AND p.material IN {MATERIALS} AND p.design_type IN {TYPES}
      AND (p.vert_clr_over_m >= {CLEAR_M})
      AND (p.vert_clr_under_ref <> 'H' OR p.vert_clr_under_m >= {CLEAR_M}))"""


def load(years) -> pl.DataFrame:
    ys = ",".join(str(y) for y in years)
    con = connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{KEYED}/nbi_*.parquet') WHERE year IN ({ys})")
    q = f"""
      SELECT f.*, y.y, y.method1, y.interval FROM (
        SELECT p.bridge_id, p.year, p.inspection_interval_mo AS interval, {method1_expr()} AS method1,
               {q4_miss_expr().replace(' AS q4_miss_48mo', ' AS y')}
        FROM p JOIN read_parquet('{LABELS}') l USING (bridge_id, year)) y
      JOIN read_parquet('{FEATURES}') f USING (bridge_id, year)
      WHERE y.y IS NOT NULL"""
    return con.execute(q).pl()


def screen(base_year: int, train_years: int = 8, hybrid_cut: float = 0.10) -> dict:
    train = load(range(base_year - 4 - train_years + 1, base_year - 4 + 1))
    test = load([base_year])
    model = GBM(name="q4_model").fit(train)
    on24 = test.filter(pl.col("interval") == 24)
    risk = model.predict(on24)
    y = on24["y"].cast(pl.Float64).to_numpy()
    m1 = on24["method1"].fill_null(False).to_numpy()
    n1 = int(m1.sum())

    order = np.argsort(risk, kind="mergesort")
    model_pick = np.zeros(len(y), bool)
    model_pick[order[:n1]] = True

    hybrid = m1.copy()
    if n1:
        idx = np.where(m1)[0]
        drop = idx[np.argsort(-risk[idx], kind="mergesort")[: round(hybrid_cut * n1)]]
        hybrid[drop] = False

    curve = []
    for frac in (0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60):
        k = round(frac * len(y))
        curve.append({"share_eligible": frac, "bridges": k, "miss_rate": float(y[order[:k]].mean())})

    already48 = test.filter(pl.col("interval") == 48)
    out = {
        "base_year": base_year,
        "on_24mo": len(y), "miss_rate_all_24mo": float(y.mean()),
        "method1": {"bridges": n1, "miss_rate": float(y[m1].mean()) if n1 else None},
        "model_same_count": {"bridges": int(model_pick.sum()), "miss_rate": float(y[model_pick].mean()) if n1 else None},
        "hybrid": {"bridges": int(hybrid.sum()), "miss_rate": float(y[hybrid].mean()) if hybrid.any() else None,
                   "removed_share_of_method1_misses": float(1 - y[hybrid].sum() / max(y[m1].sum(), 1)) if n1 else None},
        "curve_model": curve,
        "already_on_48mo": {"bridges": already48.height, "miss_rate": float(already48["y"].cast(pl.Float64).mean())
                            if already48.height else None},
    }
    return out


def run_screen(base_years=(2015, 2017, 2019, 2021)) -> list[dict]:
    out = []
    for y in base_years:
        out.append(screen(y))
        r = out[-1]
        print(f"Q4 base {y}: 24-mo {r['on_24mo']:,} miss {r['miss_rate_all_24mo']:.2%} | method1 {r['method1']['bridges']:,} "
              f"miss {r['method1']['miss_rate']:.2%} | model {r['model_same_count']['miss_rate']:.2%} | "
              f"hybrid {r['hybrid']['miss_rate']:.2%}", flush=True)
    (REPORTS / "screen.json").write_text(json.dumps(out, indent=1))
    return out
