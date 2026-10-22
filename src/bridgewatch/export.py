"""Export static data for the website (web/). No server is needed: the site reads these files directly.

Bridges are sorted by state, then by bridge_id, and every file below uses that one order, so record i in points.bin is row
(i - state start) of that state's files. No ID lookups are needed in the browser.

web/data/points.bin           12 bytes per bridge, little-endian: lon f32, lat f32, condition u8 (1 Good, 2 Fair, 3 Poor),
                              Q1 risk band u8, Q3 risk band u8, flags u8 (bit0 posted/closed, bit1 Method 1-eligible on a
                              24-month cycle, bit2 NHS). Bands 1-5: <1%, 1-3%, 3-10%, 10-25%, >25%; 0 = not applicable.
web/data/points_index.json    [[state, first record, count], ...]
web/data/states/{fips}.json   columnar: {"columns": [...], "data": {column: [values]}}; probabilities in basis points
                              (1/10,000), money in whole dollars
web/data/history/{fips}.json  [first_year, deck, super, sub, culvert, posting]: one character per year, same order
web/data/summary.json         per-state counts plus the backtest, screen and planner reports
"""

import json

import numpy as np
import polars as pl

from .db import connect
from .paths import KEYED, REPORTS, ROOT
from .score import SCORES

WEB = ROOT / "web" / "data"
COND = {"Good": 1, "Fair": 2, "Poor": 3}
BANDS = (0.01, 0.03, 0.10, 0.25)
TEXT = ["bridge_id", "nbi_id", "county_code", "carries", "crosses", "location_desc", "condition", "posting", "owner", "material",
        "design_type", "nhs"]
INTS = ["year_built", "adt", "lowest_rating", "deck", "superstructure", "substructure", "culvert", "interval"]
PROBS = ["p_poor_4y", "p_restricted_4y", "p_q4_miss_4y"]
MONEY = ["treatment_cost", "replacement_cost", "detour_cost_day"]


def band(p: np.ndarray) -> np.ndarray:
    out = np.digitize(np.nan_to_num(p, nan=-1), BANDS) + 1
    out[np.isnan(p)] = 0
    return out.astype(np.uint8)


def _grid(r: dict) -> list:
    """[first_year, deck, super, sub, culvert, posting]: one character per year from first_year to 2025.
    Ratings 0-9, "N" not applicable, "." no record that year; posting codes, "-" blank, "." no record."""
    if r["first_year"] is None:
        return [None, "", "", "", "", ""]
    n = r["last_year"] - r["first_year"] + 1
    out = [r["first_year"]]
    for key in ("d", "su", "sb", "cu", "po"):
        cells = ["."] * n
        for y, v in zip(r["yrs"], r[key], strict=True):
            cells[y - r["first_year"]] = (str(v) if v is not None else "N") if key != "po" else v
        out.append("".join(cells))
    return out


def _columnar(g: pl.DataFrame) -> dict:
    g = g.with_columns(
        *[(pl.col(c).fill_nan(None) * 10000).round(0).cast(pl.Int32) for c in PROBS],
        *[pl.col(c).round(0).cast(pl.Int64) for c in MONEY],
        (pl.col("value_per_dollar").fill_nan(None) * 1000).round(0).cast(pl.Int64).alias("value_per_dollar"),
        pl.col("lat").round(5), pl.col("lon").round(5), pl.col("method1").cast(pl.Int8), pl.col("no_detour").cast(pl.Int8),
        *[pl.col(c).cast(pl.Int32) for c in INTS])
    cols = [*TEXT, *INTS, *PROBS, *MONEY, "value_per_dollar", "lat", "lon", "method1", "no_detour"]
    return {"columns": cols, "scale": {"probabilities": 10000, "value_per_dollar": 1000},
            "data": {c: g[c].to_list() for c in cols}}


def export(year: int = 2025) -> dict:
    s = pl.read_parquet(str(SCORES).format(year=year)).filter(pl.col("lat").is_not_null()).sort("state_code", "bridge_id")
    for sub in ("states", "history"):
        (WEB / sub).mkdir(parents=True, exist_ok=True)

    flags = ((s["posting"].is_in(["P", "R", "K"]).cast(pl.UInt8))
             | (((s["method1"].fill_null(False)) & (s["interval"] == 24)).cast(pl.UInt8) * 2)
             | ((s["nhs"] == "1").cast(pl.UInt8) * 4)).fill_null(0).to_numpy()
    rec = np.zeros(s.height, dtype=[("lon", "<f4"), ("lat", "<f4"), ("c", "u1"), ("q1", "u1"), ("q3", "u1"), ("f", "u1")])
    rec["lon"], rec["lat"] = s["lon"].to_numpy(), s["lat"].to_numpy()
    rec["c"] = s["condition"].replace_strict(COND, default=0, return_dtype=pl.UInt8).fill_null(0).to_numpy()
    rec["q1"] = band(s["p_poor_4y"].to_numpy().astype(float))
    rec["q3"] = band(s["p_restricted_4y"].to_numpy().astype(float))
    rec["f"] = flags
    rec.tofile(WEB / "points.bin")

    ranges, start = [], 0
    for (st,), g in s.group_by(["state_code"], maintain_order=True):
        ranges.append([st, start, g.height])
        start += g.height
        (WEB / "states" / f"{st}.json").write_text(json.dumps(_columnar(g), separators=(",", ":")))
    (WEB / "points_index.json").write_text(json.dumps({"states": ranges, "record_bytes": 12, "bands": BANDS}))

    con = connect()
    for st, _, _ in ranges:  # one state at a time keeps the ordered aggregation small
        g = s.filter(pl.col("state_code") == st).select("bridge_id")
        con.register("ids", g.to_arrow())
        hist = con.execute(f"""
          SELECT bridge_id, min(year) AS first_year, max(year) AS last_year,
                 list(year ORDER BY year) AS yrs, list(deck ORDER BY year) AS d, list(superstructure ORDER BY year) AS su,
                 list(substructure ORDER BY year) AS sb, list(culvert ORDER BY year) AS cu,
                 list(coalesce(nullif(posting_status, ''), '-') ORDER BY year) AS po
          FROM read_parquet('{KEYED}/nbi_*.parquet') WHERE state_code = '{st}' AND bridge_id IN (SELECT bridge_id FROM ids)
          GROUP BY 1""").pl()
        hist = g.join(hist, on="bridge_id", how="left", maintain_order="left")
        rows = [_grid(r) for r in hist.iter_rows(named=True)]
        (WEB / "history" / f"{st}.json").write_text(json.dumps(rows, separators=(",", ":")))
        con.unregister("ids")

    by_state = s.group_by("state_code").agg(
        pl.len().alias("bridges"), (pl.col("condition") == "Poor").sum().alias("poor"),
        pl.col("posting").is_in(["P", "R", "K"]).sum().alias("restricted"),
        pl.col("p_poor_4y").fill_nan(None).sum().round(1).alias("expected_new_poor_4y"),
        pl.col("p_restricted_4y").fill_nan(None).sum().round(1).alias("expected_new_restricted_4y"))
    summary = {"year": year, "bridges": s.height, "by_state": by_state.sort("state_code").to_dicts()}
    for name in ("backtest", "screen", "plan"):
        f = REPORTS / f"{name}.json"
        if f.exists():
            summary[name] = json.loads(f.read_text())
    (WEB / "summary.json").write_text(json.dumps(summary, default=float, separators=(",", ":")))
    sizes = {p.name: p.stat().st_size for p in WEB.glob("*.*")}
    sizes["states_total"] = sum(p.stat().st_size for p in (WEB / "states").glob("*.json"))
    sizes["history_total"] = sum(p.stat().st_size for p in (WEB / "history").glob("*.json"))
    return {"bridges": s.height, "bytes": sizes}
