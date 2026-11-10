import json
import logging
from numbers import Real
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .common import (
    ENGINEERED,
    FEATURES,
    add_engineered_features,
    from_log,
    normalize_boolean,
    tunnel_shape_code,
)

ARTIFACT_DIR = Path("geocruncher/profiler/artifacts")
LOGGER = logging.getLogger(__name__)


class DurationPredictor:
    def __init__(self, artifact_dir=ARTIFACT_DIR):
        self.artifact_dir = Path(artifact_dir)
        meta_path = self.artifact_dir / "metadata.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"{meta_path} not found. Run train_model.py first.")
        self.meta = json.loads(meta_path.read_text())
        if self.meta.get("target_transform") != "log1p":
            raise RuntimeError(
                "Artifacts were not trained with the log1p target; retrain."
            )
        self.models = {}

    def _get_model(self, computation_type):
        if computation_type not in self.meta["computation_types"]:
            raise ValueError(
                f"No trained model for {computation_type!r}. "
                f"Available: {self.meta['computation_types']}"
            )
        if computation_type not in self.models:
            path = self.artifact_dir / f"model_{computation_type}.joblib"
            if not path.exists():
                raise FileNotFoundError(
                    f"Model not found: {path}. Run train_model.py first."
                )
            self.models[computation_type] = joblib.load(path)
        return self.models[computation_type]

    @staticmethod
    def _model_features(model):
        """Return the input columns recorded by a fitted model, when available."""
        for candidate in (
            model,
            getattr(model, "workload", None),
            getattr(model, "ml", None),
            getattr(model, "linear", None),
        ):
            features = getattr(candidate, "feature_names_in_", None)
            if features is not None:
                return list(features)
            named_steps = getattr(candidate, "named_steps", {})
            for step in named_steps.values():
                features = getattr(step, "feature_names_in_", None)
                if features is not None:
                    return list(features)
        return None

    def _log_prediction(self, factors):
        if "computation_type" not in factors:
            raise ValueError("Missing required field: computation_type")
        computation_type = factors["computation_type"]
        if not isinstance(computation_type, str):
            raise ValueError("computation_type must be a string")
        metadata_features = self.meta.get("features", {}).get(
            computation_type, FEATURES.get(computation_type)
        )
        if metadata_features is None:
            raise ValueError(
                f"Unknown computation type: {computation_type!r}. "
                f"Expected one of: {sorted(FEATURES)}"
            )
        model = self._get_model(computation_type)
        model_features = self._model_features(model)
        engineered_names = set(
            self.meta.get("engineered_features", {}).get(
                computation_type, ENGINEERED.get(computation_type, [])
            )
        )
        features = list(metadata_features)
        if model_features is not None:
            features.extend(
                name
                for name in model_features
                if name not in engineered_names and name not in features
            )

        provided_factors = dict(factors)
        if computation_type == "tunnel_meshes" and "shape" in provided_factors:
            provided_factors["shape_code"] = tunnel_shape_code(
                provided_factors["shape"]
            )
        missing = set(features) - set(provided_factors)
        if missing:
            raise ValueError(
                f"Missing features for {computation_type}: {sorted(missing)}"
            )

        row = {name: provided_factors[name] for name in features}
        if computation_type == "tunnel_meshes":
            shape = factors.get("shape")
            if shape is not None:
                shape_code = tunnel_shape_code(shape)
                if shape_code is None:
                    raise ValueError(
                        f"shape must be Circle, Rectangle, or Elliptic, got {shape!r}"
                    )
                row["shape_code"] = shape_code
        if "compute_map" in row:
            row["compute_map"] = normalize_boolean(row["compute_map"])
        for name, value in row.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not np.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"{name} must be a finite number >= 0, got {value!r}")

        frame = add_engineered_features(
            pd.DataFrame([row], columns=features), computation_type
        )
        engineered = [
            name
            for name in self.meta.get("engineered_features", {}).get(
                computation_type, []
            )
            if name in frame
        ]
        columns = list(features) + engineered
        if model_features is not None:
            missing_model_columns = set(model_features) - set(columns)
            if missing_model_columns:
                raise RuntimeError(
                    f"Model schema requires unavailable features: "
                    f"{sorted(missing_model_columns)}"
                )
            columns = model_features
        frame = frame[columns]

        log_pred = float(model.predict(frame)[0])

        # Keep extrapolated predictions close to the observed training range.
        lo, hi = self.meta["log_target_range"][computation_type]
        return computation_type, float(np.clip(log_pred, max(0.0, lo - 1.0), hi + 1.0))

    def predict(self, factors: dict) -> dict:
        """Empirical P10-P90 runtime range in seconds."""
        computation_type, log_pred = self._log_prediction(factors)
        off = self.meta["log_interval_offsets"][computation_type]
        lower = max(0.0, float(from_log(log_pred + off["lower"])))
        upper = max(0.0, float(from_log(log_pred + off["upper"])))
        p50 = max(0.0, float(from_log(log_pred + off["p50"])))
        prediction = {
            "lower": lower,
            "p10": lower,
            "p50": p50,
            "p90": upper,
            "upper": upper,
        }
        LOGGER.warning(
            "Estimated %s duration range: %.2f-%.2f seconds "
            "(typical %.2f, features=%s)",
            computation_type,
            lower,
            upper,
            p50,
            factors,
        )
        return prediction
