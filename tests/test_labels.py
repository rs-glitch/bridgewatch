import duckdb
import polars as pl

from bridgewatch import labels


def _panel(tmp_path, rows):
    cols = ["bridge_id", "year", "condition", "posting_status", "deck", "superstructure", "substructure", "culvert", "year_reconstructed"]
    df = pl.DataFrame([dict(zip(cols, r, strict=True)) for r in rows],
                      schema={"bridge_id": pl.String, "year": pl.Int16, "condition": pl.String, "posting_status": pl.String,
                              "deck": pl.Int8, "superstructure": pl.Int8, "substructure": pl.Int8, "culvert": pl.Int8,
                              "year_reconstructed": pl.Int64})
    for y in df["year"].unique():
        df.filter(pl.col("year") == y).write_parquet(tmp_path / f"nbi_{y}.parquet")
    out = tmp_path / "labels.parquet"
    labels.build_labels(tmp_path, out)
    return df, out


ROWS = [
    # A: Fair -> Poor in 2013, posted in 2014
    ("A", 2010, "Fair", "A", 6, 6, 6, None, 0), ("A", 2011, "Fair", "A", 6, 6, 5, None, 0), ("A", 2012, "Fair", "A", 6, 5, 5, None, 0),
    ("A", 2013, "Poor", "A", 6, 5, 4, None, 0), ("A", 2014, "Poor", "P", 6, 5, 4, None, 0),
    # B: stays Good, disappears after 2011 (censored)
    ("B", 2010, "Good", "A", 8, 8, 8, None, 0), ("B", 2011, "Good", "A", 8, 8, 8, None, 0),
    # C: Good, deck drops 8 -> 6 (Q4 miss without Poor), repaired 2014 (rating up 2 with new reconstruction year)
    ("C", 2010, "Good", "A", 8, 8, 8, None, 0), ("C", 2011, "Good", "A", 7, 8, 8, None, 0), ("C", 2012, "Fair", "A", 6, 7, 7, None, 0),
    ("C", 2013, "Fair", "A", 6, 7, 7, None, 0), ("C", 2014, "Good", "A", 8, 8, 8, None, 2014),
]


def _labelled(tmp_path, h):
    _, out = _panel(tmp_path, ROWS)
    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{tmp_path}/nbi_*.parquet')")
    q = f"""SELECT p.bridge_id, p.year, {labels.label_expr(h)}, {labels.q4_miss_expr()}, l.repair_year
            FROM p JOIN read_parquet('{out}') l USING (bridge_id, year) ORDER BY 1, 2"""
    return {(r[0], r[1]): r[2:] for r in con.execute(q).fetchall()}


def test_became_poor_and_restricted(tmp_path):
    lab = _labelled(tmp_path, 2)
    assert lab[("A", 2010)][:2] == (False, False)  # Poor only in 2013, outside 2010+2
    assert lab[("A", 2011)][:2] == (True, False)
    assert lab[("A", 2012)][:2] == (True, True)  # posted 2014 = 2012+2
    assert lab[("A", 2013)][0] is None  # already Poor


def test_censoring_when_bridge_leaves(tmp_path):
    lab = _labelled(tmp_path, 2)
    assert lab[("B", 2010)][:2] == (None, None)  # last seen 2011 < 2012: outcome unknown


def test_q4_miss_and_repair(tmp_path):
    lab = _labelled(tmp_path, 2)
    assert lab[("C", 2010)][2] is True  # deck 8 -> 6 within 4 years
    assert lab[("A", 2010)][2] is True  # Poor in 2013
    assert lab[("C", 2010)][3] == 2014  # repair detected
    assert lab[("C", 2013)][2] is None  # seen only to 2014 < 2017 with no event: censored
