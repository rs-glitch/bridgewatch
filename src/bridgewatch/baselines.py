"""Baselines every model must beat.

climatology      every bridge gets the training base rate (the reference for Brier skill)
rating_lookup    observed rate by current lowest rating: "rating stays the same" turned into a probability; ranks worst-first
time_in_cond     rate by lowest rating x years at that rating x material x design family, shrunk toward the rating-only rate
                 (the idea behind FHWA's time-in-condition model)
markov           one-year transition matrices per component, by material family and age band, fitted on the training years;
                 P(component reaches <= 4 within h) from the matrix power; components combined assuming independence
                 (the BrM-style approach)
"""

import numpy as np
import polars as pl

from .db import connect
from .paths import KEYED

COMPONENTS = ["deck", "superstructure", "substructure", "culvert"]


def material_family(col: str = "material") -> pl.Expr:
    m = pl.col(col)
    return (pl.when(m.is_in(["1", "2"])).then(pl.lit("concrete")).when(m.is_in(["3", "4"])).then(pl.lit("steel"))
            .when(m.is_in(["5", "6"])).then(pl.lit("prestressed")).when(m == "7").then(pl.lit("timber")).otherwise(pl.lit("other")))


def design_family(col: str = "design_type") -> pl.Expr:
    d = pl.col(col)
    return (pl.when(d == "19").then(pl.lit("culvert")).when(d == "01").then(pl.lit("slab"))
            .when(d.is_in(["02", "03", "04", "05", "06", "21", "22"])).then(pl.lit("beam"))
            .when(d.is_in(["09", "10"])).then(pl.lit("truss")).when(d.is_in(["11", "12"])).then(pl.lit("arch")).otherwise(pl.lit("other")))


def age_band(col: str = "age") -> pl.Expr:
    return pl.col(col).fill_null(40).clip(0, 120).floordiv(20).cast(pl.Int8)


class Climatology:
    name = "climatology"

    def fit(self, train):
        self.rate = float(train["y"].mean())
        return self

    def predict(self, df):
        return np.full(df.height, self.rate)


class RatingLookup:
    name = "rating_lookup"

    def fit(self, train):
        self.rate = float(train["y"].mean())
        self.table = train.group_by("lowest_rating").agg(pl.col("y").mean().alias("p"))
        return self

    def predict(self, df):
        out = df.select("lowest_rating").join(self.table, on="lowest_rating", how="left", maintain_order="left")
        return out["p"].fill_null(self.rate).to_numpy()


class TimeInCondition:
    name = "time_in_cond"
    keys = ("lowest_rating", "yrs", "mat", "des")

    def __init__(self, prior_weight: float = 50.0):
        self.m = prior_weight

    def _prep(self, df):
        return df.with_columns(pl.col("years_at_lowest").fill_null(0).clip(0, 10).alias("yrs"), material_family().alias("mat"),
                               design_family().alias("des"))

    def fit(self, train):
        t = self._prep(train)
        self.rate = float(t["y"].mean())
        self.parent = t.group_by("lowest_rating").agg(pl.col("y").mean().alias("pp"))
        self.table = t.group_by(list(self.keys)).agg(pl.col("y").sum().alias("k"), pl.len().alias("n"))
        return self

    def predict(self, df):
        t = self._prep(df).select(list(self.keys))
        t = t.join(self.table, on=list(self.keys), how="left", maintain_order="left").join(self.parent, on="lowest_rating", how="left",
                                                                                      maintain_order="left")
        pp = t["pp"].fill_null(self.rate).to_numpy()
        k, n = t["k"].fill_null(0).to_numpy(), t["n"].fill_null(0).to_numpy()
        return (k + self.m * pp) / (n + self.m)


class Markov:
    """States 5..9 are transient; <= 4 is absorbing ("Poor"). Fitted on consecutive-year pairs within the training years."""

    name = "markov"
    states = (5, 6, 7, 8, 9)

    def __init__(self, train_years, h: int, panel_dir=KEYED, exclude_states=()):
        self.years, self.h, self.panel, self.exclude = list(train_years), h, panel_dir, tuple(exclude_states)

    def fit(self, train=None):
        lo, hi = min(self.years), max(self.years)
        con = connect()
        leads = ", ".join(f"{c}, lead({c}) OVER w AS {c}_next" for c in COMPONENTS)
        skip = f"AND state_code NOT IN {self.exclude!r}".replace(",)", ")") if self.exclude else ""
        wide = con.execute(f"""
            SELECT * FROM (
              SELECT year, lead(year) OVER w AS year_next, material,
                     CASE WHEN year_built BETWEEN 1700 AND year THEN year - year_built END AS age, {leads}
              FROM read_parquet('{self.panel}/nbi_*.parquet') WHERE year BETWEEN {lo} AND {hi + 1} {skip}
              WINDOW w AS (PARTITION BY bridge_id ORDER BY year))
            WHERE year BETWEEN {lo} AND {hi} AND year_next = year + 1""").pl()
        pairs = pl.concat([wide.select("material", "age", pl.lit(c).alias("comp"), pl.col(c).alias("r0"), pl.col(f"{c}_next").alias("r1"))
                           for c in COMPONENTS]).filter((pl.col("r0") >= 5) & pl.col("r1").is_not_null())
        pairs = pairs.with_columns(material_family().alias("mat"), age_band().alias("band"),
                                   pl.when(pl.col("r1") <= 4).then(4).otherwise(pl.col("r1").clip(5, 9)).alias("r1"))
        counts = pairs.group_by(["comp", "mat", "band", "r0", "r1"]).agg(pl.len().alias("n"))
        self.matrices = {}
        glob = counts.group_by(["comp", "r0", "r1"]).agg(pl.col("n").sum())
        for (comp,), g in glob.group_by(["comp"]):
            self.matrices[(comp, None, None)] = self._matrix(g)
        for (comp, mat, band), g in counts.group_by(["comp", "mat", "band"]):
            if g["n"].sum() >= 2000:
                self.matrices[(comp, mat, band)] = self._matrix(g, prior=self.matrices[(comp, None, None)])
        self.reach = {k: np.linalg.matrix_power(m, self.h)[:, -1] for k, m in self.matrices.items()}  # P(absorbed by h)
        return self

    def _matrix(self, g, prior=None, weight: float = 20.0):
        idx = {s: i for i, s in enumerate(self.states)} | {4: len(self.states)}
        m = np.zeros((6, 6))
        for r0, r1, n in g.select("r0", "r1", "n").iter_rows():
            if r0 in idx and r1 in idx:
                m[idx[r0], idx[r1]] += n
        if prior is not None:
            m[:5] += weight * prior[:5]
        m[5, 5] = 1.0
        row = m.sum(axis=1, keepdims=True)
        row[row == 0] = 1
        m = m / row
        for i in range(5):
            if m[i].sum() == 0:
                m[i, i] = 1.0
        return m

    def predict(self, df):
        rows = [(c, mat, band, r, float(v[r - 5])) for (c, mat, band), v in self.reach.items() for r in self.states]
        table = pl.DataFrame(rows, schema={"comp": pl.String, "mat": pl.String, "band": pl.Int8, "r": pl.Int8, "p": pl.Float64},
                             orient="row")
        specific, glob = table.filter(pl.col("mat").is_not_null()), table.filter(pl.col("mat").is_null()).drop("mat", "band")
        t = df.select(*COMPONENTS, material_family().alias("mat"), age_band().alias("band")).with_row_index("i")
        survive = np.ones(t.height)
        for c in COMPONENTS:
            x = t.select("i", "mat", "band", pl.col(c).alias("r")).with_columns(pl.lit(c).alias("comp"))
            x = x.join(specific, on=["comp", "mat", "band", "r"], how="left").join(glob.rename({"p": "pg"}), on=["comp", "r"], how="left")
            x = x.sort("i")
            p = x.select(pl.when(pl.col("r") >= 5).then(pl.coalesce("p", "pg")).otherwise(0.0)).to_series().fill_null(0.0).to_numpy()
            survive *= 1 - p
        return 1 - survive
