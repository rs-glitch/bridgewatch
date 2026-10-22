"""Model features for every bridge-year, using only that year's record and the bridge's earlier records (no look-ahead).

Writes data/features.parquet keyed by (bridge_id, year). Categorical codes stay as strings; the model encodes them.
"""


from .db import connect
from .paths import DATA, KEYED

FEATURES = DATA / "features.parquet"

CATEGORICAL = ["state_code", "owner", "material", "design_type", "functional_class", "nhs", "posting_status", "deck_type",
               "wearing_surface", "membrane", "deck_protection", "scour_code", "design_load", "service_under",
               "operating_rating_method", "structural_eval", "waterway_eval"]
NUMERIC = ["deck", "superstructure", "substructure", "culvert", "channel_n", "lowest_rating", "age", "years_since_recon",
           "log_adt", "truck_pct", "log_deck_area", "max_span_m", "main_spans", "skew_deg", "lanes_on", "detour_km",
           "operating_rating_t", "inventory_rating_t", "inspection_interval_mo", "lat", "lon",
           "lowest_d2", "lowest_d4", "deck_d4", "super_d4", "sub_d4", "years_at_lowest", "drops_past8", "repairs_past8",
           "years_in_inventory"]

SQL = """
WITH p AS (
  SELECT *, try_cast(channel AS INTEGER) AS channel_n,
         lag(lowest_rating) OVER w AS low_prev, lag(year) OVER w AS year_prev,
         lag(deck) OVER w AS deck_prev, lag(superstructure) OVER w AS super_prev, lag(substructure) OVER w AS sub_prev
  FROM read_parquet('{panel}/nbi_*.parquet')
  WINDOW w AS (PARTITION BY bridge_id ORDER BY year)
), q AS (
  SELECT *,
    (lowest_rating < low_prev)::INT AS dropped_here,
    (greatest(deck - deck_prev, superstructure - super_prev, substructure - sub_prev) >= 2)::INT AS repaired_here,
    -- a new "run" starts whenever the lowest rating changes; used for years spent at the current rating
    sum((lowest_rating IS DISTINCT FROM low_prev)::INT) OVER w AS run_id
  FROM p WINDOW w AS (PARTITION BY bridge_id ORDER BY year)
)
SELECT bridge_id, year,
  {cats},
  deck, superstructure, substructure, culvert, channel_n, lowest_rating,
  CASE WHEN year_built BETWEEN 1700 AND year THEN year - year_built END AS age,
  CASE WHEN year_reconstructed BETWEEN 1700 AND year THEN year - year_reconstructed END AS years_since_recon,
  ln(1 + greatest(adt, 0)) AS log_adt,
  CASE WHEN truck_pct BETWEEN 0 AND 99 THEN truck_pct END AS truck_pct,
  ln(1 + greatest(deck_area_m2, 0)) AS log_deck_area,
  max_span_m, main_spans, skew_deg, lanes_on,
  CASE WHEN detour_km < 199 THEN detour_km END AS detour_km,
  CASE WHEN operating_rating_t < 99 THEN operating_rating_t END AS operating_rating_t,
  CASE WHEN inventory_rating_t < 99 THEN inventory_rating_t END AS inventory_rating_t,
  inspection_interval_mo, lat, lon,
  lowest_rating - max(lowest_rating) OVER (PARTITION BY bridge_id ORDER BY year RANGE BETWEEN 2 PRECEDING AND 2 PRECEDING) AS lowest_d2,
  lowest_rating - max(lowest_rating) OVER (PARTITION BY bridge_id ORDER BY year RANGE BETWEEN 4 PRECEDING AND 4 PRECEDING) AS lowest_d4,
  deck - max(deck) OVER (PARTITION BY bridge_id ORDER BY year RANGE BETWEEN 4 PRECEDING AND 4 PRECEDING) AS deck_d4,
  superstructure - max(superstructure) OVER (PARTITION BY bridge_id ORDER BY year RANGE BETWEEN 4 PRECEDING AND 4 PRECEDING) AS super_d4,
  substructure - max(substructure) OVER (PARTITION BY bridge_id ORDER BY year RANGE BETWEEN 4 PRECEDING AND 4 PRECEDING) AS sub_d4,
  year - min(year) OVER (PARTITION BY bridge_id, run_id) AS years_at_lowest,
  sum(dropped_here) OVER (PARTITION BY bridge_id ORDER BY year RANGE BETWEEN 8 PRECEDING AND CURRENT ROW) AS drops_past8,
  sum(repaired_here) OVER (PARTITION BY bridge_id ORDER BY year RANGE BETWEEN 8 PRECEDING AND CURRENT ROW) AS repairs_past8,
  year - min(year) OVER (PARTITION BY bridge_id) AS years_in_inventory
FROM q
"""


def build_features(panel_dir=KEYED, out=FEATURES) -> int:
    con = connect()
    sql = SQL.format(panel=panel_dir, cats=", ".join(CATEGORICAL))
    con.execute(f"COPY ({sql}) TO '{out}' (FORMAT parquet, COMPRESSION zstd)")
    return con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
