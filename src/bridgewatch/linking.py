"""Link bridge IDs across renumberings, so one physical bridge keeps one history.

Several states renumbered most of their inventory in a single year (e.g. Illinois 2013, Missouri 2001, Pennsylvania 2010).
For every ID that is present in year y but absent in y+1 ("gone"), we look for an ID that is new in y+1 in the same state.
Passes, in order (an ID linked by an earlier pass is not reconsidered):
  1. padding:     the structure numbers are equal after removing spaces and leading zeros (e.g. Arizona 2015: 0087 -> 00087)
  2. description: same county, year built, material, design type, main spans, length and deck width (to 0.1 m), unique in
                  both directions; if several share the description, the nearest within 300 m with the runner-up 3x farther
  3. location:    within 50 m, same material, length within 15% (or 2 m), year built within 2 years and not new,
                  clear nearest (runner-up 3x farther); this
                  catches renumberings where the description was also edited (e.g. South Carolina 2005, Alabama 1992)
Finally, links that would give one bridge two records in the same year are removed.

Output: data/id_links.parquet with (old_id, new_id, year_new, method) and data/id_map.parquet mapping every ID to a
stable `bridge_key` (the earliest ID in its chain).
"""

import polars as pl

from .db import connect
from .paths import DATA, KEYED, PANEL

LINKS = DATA / "id_links.parquet"
ID_MAP = DATA / "id_map.parquet"
KEY = ["state_code", "county_code", "year_built", "material", "design_type", "main_spans", "len_r", "wid_r"]

SQL = """
WITH p AS (SELECT bridge_id, year, state_code, county_code, year_built, material, design_type, main_spans,
                  round(length_m, 1) len_r, round(deck_width_m, 1) wid_r, lat, lon
           FROM read_parquet('{panel}/nbi_*.parquet')),
ids AS (SELECT DISTINCT bridge_id, year FROM p),
gone AS (SELECT a.* FROM p a LEFT JOIN ids b ON a.bridge_id = b.bridge_id AND b.year = a.year + 1
         WHERE b.bridge_id IS NULL AND a.year < (SELECT max(year) FROM ids)),
new AS (SELECT a.* FROM p a LEFT JOIN ids b ON a.bridge_id = b.bridge_id AND b.year = a.year - 1
        WHERE b.bridge_id IS NULL AND a.year > (SELECT min(year) FROM ids))
SELECT g.bridge_id old_id, n.bridge_id new_id, n.year year_new,
       CASE WHEN g.lat IS NULL OR n.lat IS NULL THEN NULL
            ELSE 111000 * sqrt(pow(g.lat - n.lat, 2) + pow((g.lon - n.lon) * cos(radians(g.lat)), 2)) END AS dist_m
FROM gone g JOIN new n ON n.year = g.year + 1 AND {join}
WHERE g.year_built IS NOT NULL AND g.len_r > 0 AND g.wid_r > 0
"""


LOC_SQL = """
WITH p AS (SELECT bridge_id, year, state_code, material, length_m, year_built, lat, lon FROM read_parquet('{panel}/nbi_*.parquet')),
ids AS (SELECT DISTINCT bridge_id, year FROM p),
gone AS (SELECT a.* FROM p a LEFT JOIN ids b ON a.bridge_id = b.bridge_id AND b.year = a.year + 1
         WHERE b.bridge_id IS NULL AND a.lat IS NOT NULL),
new AS (SELECT a.* FROM p a LEFT JOIN ids b ON a.bridge_id = b.bridge_id AND b.year = a.year - 1
        WHERE b.bridge_id IS NULL AND a.lat IS NOT NULL)
SELECT g.bridge_id old_id, n.bridge_id new_id, n.year year_new,
       111000 * sqrt(pow(g.lat - n.lat, 2) + pow((g.lon - n.lon) * cos(radians(g.lat)), 2)) AS dist_m
FROM gone g JOIN new n ON n.year = g.year + 1 AND n.state_code = g.state_code AND n.material = g.material
  AND abs(n.lat - g.lat) < 0.0006 AND abs(n.lon - g.lon) < 0.0008
  AND abs(n.length_m - g.length_m) <= greatest(2, 0.15 * g.length_m)
  -- a structure built in the transition year is a replacement, not a renumbering
  AND n.year_built < n.year - 1 AND abs(n.year_built - g.year_built) <= 2
"""

PAD_SQL = """
WITH p AS (SELECT bridge_id, year, state_code,
                  state_code || '-' || ltrim(replace(structure_number, ' ', ''), '0') AS norm
           FROM read_parquet('{panel}/nbi_*.parquet')),
ids AS (SELECT DISTINCT bridge_id, year FROM p),
gone AS (SELECT a.* FROM p a LEFT JOIN ids b ON a.bridge_id = b.bridge_id AND b.year = a.year + 1 WHERE b.bridge_id IS NULL),
new AS (SELECT a.* FROM p a LEFT JOIN ids b ON a.bridge_id = b.bridge_id AND b.year = a.year - 1 WHERE b.bridge_id IS NULL)
SELECT g.bridge_id old_id, n.bridge_id new_id, n.year year_new, NULL::DOUBLE AS dist_m
FROM gone g JOIN new n ON n.year = g.year + 1 AND n.norm = g.norm
"""


def _clear_nearest(c: pl.DataFrame, max_m: float) -> pl.DataFrame:
    c = c.filter(pl.col("dist_m").is_not_null()).sort("dist_m").with_columns(
        pl.col("dist_m").rank("ordinal").over(["old_id", "year_new"]).alias("rk"),
        pl.col("dist_m").shift(-1).over(["old_id", "year_new"]).alias("next_d"),
        pl.col("dist_m").rank("ordinal").over(["new_id", "year_new"]).alias("rk_new"))
    return c.filter((pl.col("rk") == 1) & (pl.col("rk_new") == 1) & (pl.col("dist_m") <= max_m)
                    & (pl.col("next_d").is_null() | (pl.col("next_d") >= 3 * pl.col("dist_m") + 1)))


def _unique_both(c: pl.DataFrame) -> pl.DataFrame:
    a = c.group_by("old_id", "year_new").agg(pl.len().alias("n_old"))
    b = c.group_by("new_id", "year_new").agg(pl.len().alias("n_new"))
    return c.join(a, on=["old_id", "year_new"]).join(b, on=["new_id", "year_new"])


def build_links(panel_dir=PANEL, links_out=LINKS, map_out=ID_MAP) -> dict:
    con = connect()
    cols = ["old_id", "new_id", "year_new", "dist_m", "method"]
    taken_old, taken_new, parts, stats = set(), set(), [], {}

    def add(df: pl.DataFrame, method: str):
        df = df.filter(~pl.col("old_id").is_in(list(taken_old)) & ~pl.col("new_id").is_in(list(taken_new))
                       & (pl.col("old_id") != pl.col("new_id")))
        df = df.with_columns(pl.lit(method).alias("method")).select(cols)
        taken_old.update(df["old_id"].to_list())
        taken_new.update(df["new_id"].to_list())
        parts.append(df)
        stats[f"links_{method}"] = df.height

    pad = _unique_both(con.execute(PAD_SQL.format(panel=panel_dir)).pl())
    add(pad.filter((pl.col("n_old") == 1) & (pl.col("n_new") == 1)), "padding")

    join = " AND ".join(f"g.{k} = n.{k}" for k in KEY)
    desc = _unique_both(con.execute(SQL.format(panel=panel_dir, join=join)).pl())
    add(desc.filter((pl.col("n_old") == 1) & (pl.col("n_new") == 1)), "description")
    add(_clear_nearest(desc.filter((pl.col("n_old") > 1) | (pl.col("n_new") > 1)), 300), "description_nearest")

    add(_clear_nearest(con.execute(LOC_SQL.format(panel=panel_dir)).pl(), 50), "location")

    links = pl.concat(parts)
    parent = dict(zip(links["new_id"].to_list(), links["old_id"].to_list(), strict=True))

    def root(i, depth=0):
        while i in parent and depth < 40:
            i, depth = parent[i], depth + 1
        return i

    years = con.execute(f"SELECT DISTINCT bridge_id, year FROM read_parquet('{panel_dir}/nbi_*.parquet')").pl()
    # remove links whose chain would put two records of one bridge in the same year, then recompute
    for _ in range(3):
        keyed = years.with_columns(pl.col("bridge_id").map_elements(root, return_dtype=pl.String).alias("k"))
        bad_keys = keyed.group_by("k", "year").agg(pl.len().alias("n")).filter(pl.col("n") > 1)["k"].unique().to_list()
        if not bad_keys:
            break
        bad_ids = set(keyed.filter(pl.col("k").is_in(bad_keys))["bridge_id"].to_list())
        links = links.filter(~pl.col("new_id").is_in(list(bad_ids)))
        parent = dict(zip(links["new_id"].to_list(), links["old_id"].to_list(), strict=True))
        stats["links_removed_for_collisions"] = stats.get("links_removed_for_collisions", 0) + len(bad_ids)
    links.write_parquet(links_out)
    ids = years["bridge_id"].unique().to_list()
    pl.DataFrame({"bridge_id": ids, "bridge_key": [root(i) for i in ids]}).write_parquet(map_out)
    return stats | {"links_total": links.height, "ids": len(ids), "keys": len({root(i) for i in ids})}


def apply_keys(panel_dir=PANEL, map_path=ID_MAP, out_dir=KEYED) -> int:
    """Write data/panel_keyed/nbi_{year}.parquet: bridge_id = stable key, nbi_id = the ID as published that year."""
    out_dir.mkdir(parents=True, exist_ok=True)
    con = connect()
    years = sorted(int(f.stem.split("_")[1]) for f in panel_dir.glob("nbi_*.parquet"))
    for y in years:
        con.execute(f"""COPY (SELECT m.bridge_key AS bridge_id, p.bridge_id AS nbi_id, p.* EXCLUDE (bridge_id)
                             FROM read_parquet('{panel_dir}/nbi_{y}.parquet') p JOIN read_parquet('{map_path}') m USING (bridge_id))
                        TO '{out_dir}/nbi_{y}.parquet' (FORMAT parquet, COMPRESSION zstd)""")
    return len(years)
