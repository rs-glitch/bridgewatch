"""Features at year t must not change when later years are removed (no look-ahead)."""

import polars as pl

from bridgewatch import features
from bridgewatch.features import CATEGORICAL

BASE = {c: "1" for c in CATEGORICAL} | {"state_code": "19", "channel": "N", "year_built": 1960, "year_reconstructed": 0,
                                        "adt": 400, "truck_pct": 10, "deck_area_m2": 120.0, "max_span_m": 12.0, "main_spans": 2,
                                        "skew_deg": 0, "lanes_on": 2, "detour_km": 5.0, "operating_rating_t": 40.0,
                                        "inventory_rating_t": 30.0, "inspection_interval_mo": 24, "lat": 42.0, "lon": -93.0,
                                        "culvert": None}
RATINGS = {2010: (7, 7, 7), 2011: (7, 6, 7), 2012: (6, 6, 6), 2013: (6, 6, 5), 2014: (8, 8, 8), 2015: (8, 8, 7)}


def _write(tmp, years):
    rows = [BASE | {"bridge_id": "19-1", "year": y, "deck": d, "superstructure": s, "substructure": b,
                    "lowest_rating": min(d, s, b)} for y, (d, s, b) in RATINGS.items() if y in years]
    df = pl.DataFrame(rows)
    for y in years:
        df.filter(pl.col("year") == y).write_parquet(tmp / f"nbi_{y}.parquet")


def test_no_look_ahead(tmp_path):
    full, cut = tmp_path / "full", tmp_path / "cut"
    full.mkdir()
    cut.mkdir()
    _write(full, list(RATINGS))
    _write(cut, [2010, 2011, 2012, 2013])
    features.build_features(full, tmp_path / "f_full.parquet")
    features.build_features(cut, tmp_path / "f_cut.parquet")
    a = pl.read_parquet(tmp_path / "f_full.parquet").filter(pl.col("year") <= 2013).sort("year")
    b = pl.read_parquet(tmp_path / "f_cut.parquet").sort("year")
    assert a.equals(b)
    row = b.filter(pl.col("year") == 2013).row(0, named=True)
    assert row["lowest_rating"] == 5 and row["lowest_d2"] == -1 and row["years_at_lowest"] == 0
    assert row["age"] == 53 and row["drops_past8"] == 2 and row["years_in_inventory"] == 3


def test_repair_counted(tmp_path):
    _write(tmp_path, list(RATINGS))
    features.build_features(tmp_path, tmp_path / "f.parquet")
    r = pl.read_parquet(tmp_path / "f.parquet").filter(pl.col("year") == 2015).row(0, named=True)
    assert r["repairs_past8"] == 1 and r["lowest_d4"] == 1  # lowest 6 in 2011 -> 7 in 2015
