"""Gradient-boosted risk model for Q1 (became Poor) and Q3 (became posted/restricted/closed).

scikit-learn HistGradientBoostingClassifier on the past-only features. Categorical codes are mapped to integers learned on the
training rows (unseen or rare codes become missing). Risk may never fall as a condition rating gets worse (monotone
constraint on the ratings), so the model cannot learn a "worse rating, lower risk" artefact from noisy labels.
"""

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier

from .features import CATEGORICAL, NUMERIC

MONOTONE_DOWN = {"deck", "superstructure", "substructure", "culvert", "lowest_rating"}


class GBM:
    def __init__(self, name: str = "gbm", max_iter: int = 1000, learning_rate: float = 0.06, max_leaf_nodes: int = 63,
                 min_count: int = 50, seed: int = 0):
        self.name, self.min_count, self.seed = name, min_count, seed
        self.params = {"max_iter": max_iter, "learning_rate": learning_rate, "max_leaf_nodes": max_leaf_nodes}

    def _encode(self, df: pl.DataFrame) -> np.ndarray:
        cols = []
        for c in CATEGORICAL:
            m = self.codes[c]
            cols.append(df[c].replace_strict(m, default=None, return_dtype=pl.Float64).to_numpy())
        for c in NUMERIC:
            cols.append(df[c].cast(pl.Float64).to_numpy())
        return np.column_stack(cols)

    def fit(self, train: pl.DataFrame):
        self.codes = {}
        for c in CATEGORICAL:
            vc = train[c].value_counts().filter(pl.col("count") >= self.min_count).sort("count", descending=True)
            self.codes[c] = {v: float(i) for i, v in enumerate(vc[c].to_list()[:250]) if v is not None}
        x, y = self._encode(train), train["y"].cast(pl.Int8).to_numpy()
        names = CATEGORICAL + NUMERIC
        mono = [(-1 if n in MONOTONE_DOWN else 0) for n in names]
        self.clf = HistGradientBoostingClassifier(
            **self.params, categorical_features=list(range(len(CATEGORICAL))), monotonic_cst=mono, early_stopping=True,
            validation_fraction=0.1, n_iter_no_change=30, l2_regularization=1.0, random_state=self.seed)
        self.clf.fit(x, y)
        self.feature_names = names
        return self

    def predict(self, df: pl.DataFrame) -> np.ndarray:
        return self.clf.predict_proba(self._encode(df))[:, 1]
