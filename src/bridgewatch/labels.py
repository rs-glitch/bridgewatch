"""Outcome labels for every bridge-year, computed from the bridge's own future records.

For each bridge in year t we store when things next happen, so any horizon h can be labelled later without recomputing:
  next_poor_year        first later year rated Poor (Q1)
  next_restricted_year  first later year posted for load (P), otherwise restricted (R) or closed (K) (Q3)
  last_seen_year        last year the bridge ID appears; later years are censored (replaced, renumbered or removed)
  min_{component}_4y    lowest later rating within t+1..t+4, for the Q4 "miss" event (a drop of 2 or more points)
  repair_year           first later year with a detected repair (a rating rise of 2+ in one step, or of 1+ with a new
                        reconstruction year). Internal only: used to explain label noise, not shown as a feature

Labels at horizon h (see `label_expr`):
  became_poor_h:       not Poor at t, and Poor in (t, t+h]. Null if already Poor at t, or if the bridge left the inventory
                       before t+h without having become Poor (outcome unknown).
  became_restricted_h: open (A) at t, then P/R/K in (t, t+h]. Null if not open at t, or censored as above.
"""


from .db import connect
from .paths import DATA, KEYED

LABELS = DATA / "labels.parquet"
RESTRICTED = ("P", "R", "K")
COMPONENTS = ("deck", "superstructure", "substructure", "culvert")

SQL = """
WITH p AS (
  SELECT bridge_id, year, condition, posting_status, deck, superstructure, substructure, culvert, year_reconstructed,
         lag(year) OVER w AS prev_year, lag(year_reconstructed) OVER w AS prev_recon,
         lag(deck) OVER w AS prev_deck, lag(superstructure) OVER w AS prev_super, lag(substructure) OVER w AS prev_sub
  FROM read_parquet('{panel}/nbi_*.parquet')
  WINDOW w AS (PARTITION BY bridge_id ORDER BY year)
), r AS (
  SELECT *,
    (greatest(deck - prev_deck, superstructure - prev_super, substructure - prev_sub) >= 2
     OR (greatest(deck - prev_deck, superstructure - prev_super, substructure - prev_sub) >= 1
         AND year_reconstructed > coalesce(prev_recon, 0) AND year_reconstructed >= prev_year)) AS repair_here
  FROM p
)
SELECT bridge_id, year,
  min(CASE WHEN condition = 'Poor' THEN year END) OVER f AS next_poor_year,
  min(CASE WHEN posting_status IN {restricted} THEN year END) OVER f AS next_restricted_year,
  max(year) OVER (PARTITION BY bridge_id) AS last_seen_year,
  min(CASE WHEN repair_here THEN year END) OVER f AS repair_year,
  {mins}
FROM r
WINDOW f AS (PARTITION BY bridge_id ORDER BY year ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING),
       f4 AS (PARTITION BY bridge_id ORDER BY year RANGE BETWEEN 1 FOLLOWING AND 4 FOLLOWING)
"""


def build_labels(panel_dir=KEYED, out=LABELS) -> int:
    mins = ",\n  ".join(f"min({c}) OVER f4 AS min_{c}_4y" for c in COMPONENTS)
    sql = SQL.format(panel=panel_dir, restricted=RESTRICTED, mins=mins)
    con = connect()
    con.execute(f"COPY ({sql}) TO '{out}' (FORMAT parquet, COMPRESSION zstd)")
    return con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]


def label_expr(h: int) -> str:
    """SQL select-list for horizon h. Expects the panel joined to labels as `p` and `l`."""
    return f"""
    CASE WHEN p.condition = 'Poor' OR p.condition IS NULL THEN NULL
         WHEN l.next_poor_year <= p.year + {h} THEN TRUE
         WHEN l.last_seen_year < p.year + {h} THEN NULL
         ELSE FALSE END AS became_poor_{h},
    CASE WHEN p.posting_status <> 'A' OR p.posting_status IS NULL THEN NULL
         WHEN l.next_restricted_year <= p.year + {h} THEN TRUE
         WHEN l.last_seen_year < p.year + {h} THEN NULL
         ELSE FALSE END AS became_restricted_{h}"""


def q4_miss_expr() -> str:
    """Q4 miss event within 48 months: Poor, restricted/closed, or any component down 2+ points from year t."""
    drops = " OR ".join(f"(p.{c} - l.min_{c}_4y >= 2)" for c in COMPONENTS)
    return f"""
    CASE WHEN l.last_seen_year < p.year + 4 AND NOT coalesce(l.next_poor_year <= p.year + 4
              OR l.next_restricted_year <= p.year + 4 OR {drops}, FALSE) THEN NULL
         ELSE coalesce(l.next_poor_year <= p.year + 4 OR l.next_restricted_year <= p.year + 4 OR {drops}, FALSE)
    END AS q4_miss_48mo"""
