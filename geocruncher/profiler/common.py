"""Definitions shared by the profiler training and prediction modules."""

from numbers import Real

import numpy as np
from catboost import CatBoostRegressor
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

TARGET = "Total Computation Time"

FEATURES = {
    "tunnel_meshes": ["num_waypoints", "shape_code"],
    "faults": [
        "num_infinite_faults",
        "num_fault_unit_pairs",
        "num_dips",
        "resolution",
        "resolution_x",
        "resolution_y",
        "resolution_z",
        "box_size_x",
        "box_size_y",
        "box_size_z",
        "box_volume",
        "num_finite_faults",
        "num_contact_data",
        "num_stops_on_relations",
    ],
    "gwb_meshes": [
        "num_units",
        "num_springs",
        "total_mesh_bytes",
        "mesh_bytes_per_unit",
    ],
    "intersections": [
        "num_units",
        "num_fault_unit_pairs",
        "num_infinite_faults",
        "num_dips",
        "box_size_x",
        "box_size_y",
        "box_size_z",
        "box_volume",
        "num_finite_faults",
        "num_contact_data",
        "num_erode_series",
        "num_onlap_series",
        "num_stops_on_relations",
        "num_gwb_parts",
        "compute_map",
        "num_springs",
        "num_drillholes",
        "num_sections",
    ],
    "meshes": [
        "num_units",
        "num_fault_unit_pairs",
        "num_infinite_faults",
        "num_dips",
        "resolution",
        "resolution_x",
        "resolution_y",
        "resolution_z",
        "box_size_x",
        "box_size_y",
        "box_size_z",
        "box_volume",
        "num_finite_faults",
        "num_contact_data",
        "num_erode_series",
        "num_onlap_series",
        "num_stops_on_relations",
    ],
    "voxels": [
        "num_units",
        "num_fault_unit_pairs",
        "resolution",
        "resolution_x",
        "resolution_y",
        "resolution_z",
        "box_size_x",
        "box_size_y",
        "box_size_z",
        "box_volume",
        "num_erode_series",
        "num_onlap_series",
        "num_gwb_parts",
    ],
}

TUNNEL_SHAPES = {"circle": 0, "rectangle": 1, "elliptic": 2}


def tunnel_shape_code(value):
    value = getattr(value, "value", value)
    return TUNNEL_SHAPES.get(str(value).strip().lower())


# Extra columns calculated from the raw inputs before training or prediction.
ENGINEERED = {
    "tunnel_meshes": [],
    "faults": ["faults_total"],
    "gwb_meshes": [],
    "intersections": [
        "faults_total",
        "series_total",
        "has_sections",
        "has_drillholes",
        "has_springs",
        "has_gwb",
    ],
    "meshes": [
        "faults_total",
        "series_total",
    ],
    "voxels": ["series_total"],
}

ENGINEERED_REQUIREMENTS = {
    "faults_total": ("num_infinite_faults", "num_finite_faults"),
    "series_total": ("num_erode_series", "num_onlap_series"),
    "has_sections": ("num_sections",),
    "has_drillholes": ("num_drillholes",),
    "has_springs": ("num_springs",),
    "has_gwb": ("num_gwb_parts",),
}


def all_features(computation_type):
    return FEATURES[computation_type] + ENGINEERED[computation_type]


def add_engineered_features(df, t):
    df = df.copy()
    if t in ("faults", "meshes", "intersections") and all(
        column in df for column in ENGINEERED_REQUIREMENTS["faults_total"]
    ):
        df["faults_total"] = df["num_infinite_faults"] + df["num_finite_faults"]
    if t in ("meshes", "intersections", "voxels") and all(
        column in df for column in ENGINEERED_REQUIREMENTS["series_total"]
    ):
        df["series_total"] = df["num_erode_series"] + df["num_onlap_series"]
    if t == "intersections":
        for name in ENGINEERED[t][2:]:
            source = ENGINEERED_REQUIREMENTS[name][0]
            if source in df:
                df[name] = (df[source] > 0).astype(int)
    return df


def to_log(y):
    return np.log1p(np.asarray(y, dtype=float))


def from_log(z):
    return np.expm1(np.asarray(z, dtype=float))


def normalize_boolean_column(series):
    mapping = {"true": 1, "false": 0, "1": 1, "0": 0, "yes": 1, "no": 0}
    return series.astype(str).str.strip().str.lower().map(mapping)


def normalize_boolean(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, Real) and value in (0, 1):
        return int(value)
    if isinstance(value, str):
        mapping = {"true": 1, "false": 0, "1": 1, "0": 0, "yes": 1, "no": 0}
        key = value.strip().lower()
        if key in mapping:
            return mapping[key]
    raise ValueError(f"Invalid boolean value: {value!r}")


def make_ridge():
    """Model that captures broad workload trends and can extrapolate."""
    return make_pipeline(
        FunctionTransformer(np.log1p),
        StandardScaler(),
        RidgeCV(alphas=np.logspace(-3, 3, 25)),
    )


def make_extra_trees():
    """Tree ensemble that captures non-linear relationships in the data."""
    return make_pipeline(
        FunctionTransformer(np.log1p),
        ExtraTreesRegressor(
            n_estimators=300,
            min_samples_leaf=2,
            max_features=0.8,
            random_state=42,
            n_jobs=-1,
        ),
    )


class NearestRunModel(BaseEstimator, RegressorMixin):
    """Estimate a duration from the most similar historical runs."""

    def fit(self, X, y_log):
        self.X_ = np.log1p(np.asarray(X, dtype=float))
        self.y_ = np.asarray(y_log, dtype=float)
        self.scale_ = np.maximum(np.std(self.X_, axis=0), 0.25)
        return self

    def predict(self, X):
        values = np.log1p(np.asarray(X, dtype=float))
        result = []
        for row in values:
            distances = np.sqrt(np.mean(((self.X_ - row) / self.scale_) ** 2, axis=1))
            count = min(25, len(distances))
            nearest = np.argpartition(distances, count - 1)[:count]
            weights = 1.0 / np.maximum(distances[nearest], 0.05)
            order = np.argsort(self.y_[nearest])
            sorted_y = self.y_[nearest][order]
            sorted_weights = weights[order]
            result.append(
                sorted_y[np.searchsorted(np.cumsum(sorted_weights), weights.sum() / 2)]
            )
        return np.asarray(result)


class BlendModel(BaseEstimator, RegressorMixin):
    """Combine ridge, extra trees, and similar past runs."""

    def __init__(self, workload, ml, nearest, weights):
        self.workload = workload
        self.ml = ml
        self.nearest = nearest
        self.weights = weights

    def predict(self, X):
        predictions = np.column_stack(
            [
                self.workload.predict(X),
                self.ml.predict(X),
                self.nearest.predict(X),
            ]
        )
        return predictions @ np.asarray(self.weights)


HYBRID_PARAMS = {
    "loss_function": "RMSE",
    "iterations": 300,
    "learning_rate": 0.05,
    "depth": 4,
    "l2_leaf_reg": 10,
    "verbose": False,
    "random_seed": 42,
    "allow_writing_files": False,
}


class HybridModel:
    """Use ridge regression for broad trends and a CatBoost model for residuals."""

    def fit(self, X, y_log):
        self.linear = make_ridge().fit(X, y_log)
        residual = np.asarray(y_log, dtype=float) - self.linear.predict(X)
        self.cat = CatBoostRegressor(**HYBRID_PARAMS)
        self.cat.fit(X, residual)
        return self

    def predict(self, X):
        return self.linear.predict(X) + self.cat.predict(X)
