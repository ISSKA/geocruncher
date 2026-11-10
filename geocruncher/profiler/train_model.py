import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error

from .common import (
    ENGINEERED,
    ENGINEERED_REQUIREMENTS,
    FEATURES,
    TARGET,
    BlendModel,
    HybridModel,
    NearestRunModel,
    add_engineered_features,
    from_log,
    make_extra_trees,
    make_ridge,
    normalize_boolean_column,
    to_log,
    tunnel_shape_code,
)
from .export_data import export_from_config

DATA_DIR = Path("geocruncher/profiler/data")
ARTIFACT_DIR = Path("geocruncher/profiler/artifacts")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_TRANSFORM = "log1p"

# Evaluation is split into N_CHUNKS time blocks, which are used for training and then validation of earlier blocks
N_CHUNKS = 5
KINDS = ["catboost", "ridge", "hybrid", "extra_trees"]
SELECTION_METRIC = "malr"  # median absolute log ratio, MAE but in log space
EPS = 1e-3
INTERVAL_QUANTILES = (0.10, 0.50, 0.90)

MODEL_PARAMS = {
    "loss_function": "RMSE",
    "iterations": 2000,
    "learning_rate": 0.05,
    "depth": 6,
    "verbose": False,
    "random_seed": 42,
    "allow_writing_files": False,
}
TYPE_PARAMS = {
    "intersections": {"iterations": 6000, "learning_rate": 0.08, "depth": 8},
    "meshes": {"iterations": 3000, "learning_rate": 0.05, "depth": 6},
    "gwb_meshes": {"learning_rate": 0.03, "depth": 3, "l2_leaf_reg": 10},
}
EARLY_STOP_ROUNDS = 100
# Reserve the most most recent 15% of rows for validation
VAL_FRACTION = 0.15
SMALL_N = 150
SMALL_PARAMS = {"iterations": 400, "learning_rate": 0.03, "depth": 4, "l2_leaf_reg": 10}


def report(y, p):
    y = np.asarray(y, dtype=float)
    p = np.maximum(np.asarray(p, dtype=float), 0.0)
    ratio = (p + EPS) / (y + EPS)
    return {
        "mae": float(mean_absolute_error(y, p)),
        "mdape": float(np.median(np.abs(p - y) / y)),
        "malr": float(np.mean(np.abs(np.log(ratio)))),
        "median_ratio": float(np.median(ratio)),
        "sum_ratio": float(p.sum() / y.sum()),
        "within_1.5x": float(np.mean((ratio > 1 / 1.5) & (ratio < 1.5))),
    }


def fmt(m):
    return (
        f"MAE={m['mae']:.3f}s  MdAPE={m['mdape']:.1%}  MALR={m['malr']:.2f}  "
        f"med_ratio={m['median_ratio']:.2f}  sum_ratio={m['sum_ratio']:.2f}  "
        f"within1.5x={m['within_1.5x']:.1%}"
    )


def load_data():
    files = sorted(DATA_DIR.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {DATA_DIR.resolve()}")

    frames = []
    feature_sets = {}
    for path in files:
        computation_type = path.stem
        features = FEATURES.get(computation_type)
        if features is None:
            print(f"Skipping unknown computation type: {path.name}")
            continue

        df = pd.read_csv(path, sep=None, engine="python")
        n_rows = len(df)
        df.columns = df.columns.str.strip()

        for column in features:
            if column == "compute_map" and column in df:
                df[column] = normalize_boolean_column(df[column])
            elif column in df:
                df[column] = pd.to_numeric(df[column], errors="coerce")

        available_features = [
            feature
            for feature in features
            if feature in df and df[feature].notna().any()
        ]
        missing_features = set(features) - set(available_features)
        if missing_features:
            print(
                f"{path.name}: ignoring features with no values "
                f"{sorted(missing_features)}"
            )
        feature_sets[computation_type] = available_features

        required = [TARGET, "start_time", *available_features]
        if computation_type == "tunnel_meshes":
            required.append("shape")
        missing = set(required) - set(df.columns)
        if missing:
            raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")

        df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce") / 1000
        df["start_ms"] = pd.to_numeric(df["start_time"], errors="coerce")

        if computation_type == "tunnel_meshes":
            if "shape" not in df.columns:
                raise ValueError(f"{path.name} is missing columns: ['shape']")
            df["shape_code"] = df["shape"].map(tunnel_shape_code)
            if not df["shape_code"].notna().all():
                available_features = [
                    feature for feature in available_features if feature != "shape_code"
                ]

        validation_columns = [TARGET, "start_ms"]
        for column in validation_columns:
            df[column] = df[column].replace([np.inf, -np.inf], np.nan)

        df = df.dropna(subset=validation_columns)
        df = df[df[TARGET] > 0].copy()
        df["start_ms"] = df["start_ms"].astype("int64")
        df["computation_type"] = computation_type
        frames.append(df)

        print(f"{path.name}: {len(df)} valid runs out of {n_rows} rows")

    if not frames:
        raise ValueError("No recognized computation CSV files found.")
    return pd.concat(frames, ignore_index=True), feature_sets


def make_params(computation_type, small, iterations=None):
    params = dict(MODEL_PARAMS)
    params.update(TYPE_PARAMS.get(computation_type, {}))
    if small:
        params.update(SMALL_PARAMS)
    if iterations is not None:
        params["iterations"] = iterations
    return params


def fit_candidate(kind, computation_type, small, X, y, final_iters=None):
    """Fit one candidate on log seconds. X must be sorted by time.

    Returns (model, trees_used). trees_used is only meaningful for catboost.
    """
    y_log = to_log(y)
    if kind == "ridge":
        return make_ridge().fit(X, y_log), None
    if kind == "hybrid":
        return HybridModel().fit(X, y_log), None
    if kind == "extra_trees":
        return make_extra_trees().fit(X, y_log), None

    params = make_params(computation_type, small, final_iters)
    model = CatBoostRegressor(**params)
    if small or final_iters is not None:
        model.fit(X, y_log)
        return model, params["iterations"]

    n_val = max(1, int(len(X) * VAL_FRACTION))
    model.fit(
        X.iloc[:-n_val],
        y_log[:-n_val],
        eval_set=(X.iloc[-n_val:], y_log[-n_val:]),
        use_best_model=True,
        early_stopping_rounds=EARLY_STOP_ROUNDS,
    )
    return model, int(model.get_best_iteration()) + 1


def mean_from_log_pred(log_pred, residual_quantiles):
    """Compute the mean prediction in seconds from a log-space prediction and residual quantiles."""
    shifted = log_pred[:, None] + residual_quantiles[None, :]
    return np.maximum(0.0, np.expm1(shifted).mean(axis=1))


def choose_blend(y_log, predictions):
    """Choose coarse non-negative log-space weights for the three models.
    Returns the weights with the lowest malr on the given predictions.
    """
    best_score = float("inf")
    best_weights = np.array([0.0, 1.0, 0.0])
    for workload_weight in range(11):
        for nearest_weight in range(11 - workload_weight):
            weights = (
                np.array(
                    [
                        workload_weight,
                        10 - workload_weight - nearest_weight,
                        nearest_weight,
                    ],
                    dtype=float,
                )
                / 10
            )
            blended = np.column_stack(predictions) @ weights
            score = report(from_log(y_log), from_log(blended))["malr"]
            if score < best_score:
                best_score = score
                best_weights = weights
    return best_weights


def train_models(refresh_data: bool = False):
    """Train and save all duration models from the exported profiler data."""
    if refresh_data:
        export_from_config(DATA_DIR)
    data, feature_sets = load_data()

    all_results = []
    evaluation = {}
    chosen = {}
    residual_store = {}
    interval_store = {}
    log_range = {}

    for computation_type, group in data.groupby("computation_type", sort=True):
        group = group.sort_values("start_ms", kind="stable").reset_index(drop=True)
        raw_features = feature_sets[computation_type]
        # Older profiler rows may not have recently added metadata. Use the
        # median from newer rows so those rows remain usable for training.
        for feature in raw_features:
            group[feature] = group[feature].fillna(group[feature].median())
        group = add_engineered_features(group, computation_type)
        engineered_features = [
            feature
            for feature in ENGINEERED[computation_type]
            if all(
                source in raw_features for source in ENGINEERED_REQUIREMENTS[feature]
            )
        ]
        features = raw_features + engineered_features
        small = len(group) < SMALL_N

        chunks = np.array_split(np.arange(len(group)), N_CHUNKS)
        if min(len(c) for c in chunks) < 3:
            print(
                f"Skipping {computation_type}: too few runs for {N_CHUNKS} time blocks"
            )
            continue

        X = group[features]
        y = group[TARGET]

        oof = {kind: np.full(len(group), np.nan) for kind in KINDS}
        oof["nearest"] = np.full(len(group), np.nan)
        baseline = np.full(len(group), np.nan)
        best_iters = []

        print(
            f"\n--- {computation_type} ({len(group)} runs, "
            f"{len(features)} features, forward-chaining x{N_CHUNKS - 1}) ---"
        )

        for k in range(1, N_CHUNKS):
            tr = np.concatenate(chunks[:k])
            te = chunks[k]
            X_tr, y_tr = X.iloc[tr], y.iloc[tr]
            for kind in KINDS:
                model, n_trees = fit_candidate(
                    kind, computation_type, small, X_tr, y_tr
                )
                # Predict on the test set and clip predictions to a reasonable range based on the training data.
                y_log_tr = to_log(y_tr)
                oof[kind][te] = np.clip(
                    model.predict(X.iloc[te]),
                    max(0.0, y_log_tr.min() - 1.0),
                    y_log_tr.max() + 1.0,
                )
                if kind == "catboost":
                    best_iters.append(n_trees)
            nearest = NearestRunModel().fit(X_tr, to_log(y_tr))
            oof["nearest"][te] = nearest.predict(X.iloc[te])
            baseline[te] = y_tr.median()

        scored = ~np.isnan(oof["catboost"])
        y_s = y[scored].to_numpy()

        metrics = {kind: report(y_s, from_log(oof[kind][scored])) for kind in KINDS}
        metrics["baseline"] = report(y_s, baseline[scored])
        for name, m in metrics.items():
            print(f"  {name:<9} {fmt(m)}")

        best = min(KINDS, key=lambda kind: metrics[kind][SELECTION_METRIC])
        blend_weights = choose_blend(
            to_log(y_s),
            [oof["ridge"][scored], oof[best][scored], oof["nearest"][scored]],
        )
        blend_log = (
            np.column_stack(
                [oof["ridge"][scored], oof[best][scored], oof["nearest"][scored]]
            )
            @ blend_weights
        )
        blend_metrics = report(y_s, from_log(blend_log))
        use_blend = blend_metrics[SELECTION_METRIC] < metrics[best][SELECTION_METRIC]
        chosen[computation_type] = "blend" if use_blend else best
        selected_log = blend_log if use_blend else oof[best][scored]
        if use_blend:
            print(f"  blend      {fmt(blend_metrics)} weights={blend_weights.tolist()}")
        print(
            f"  -> selected: {chosen[computation_type]} (lowest {SELECTION_METRIC}; chosen on the same "
            "scores it is reported on, so treat it as slightly optimistic)"
        )

        # Store how much the selected model usually gets wrong
        resid = to_log(y_s) - selected_log
        q = np.quantile(resid, np.linspace(0.005, 0.995, 100))
        residual_store[computation_type] = q.tolist()
        p10, p50, p90 = np.quantile(resid, INTERVAL_QUANTILES)
        interval_store[computation_type] = {
            "p10": float(p10),
            "p50": float(p50),
            "p90": float(p90),
        }
        interval_store[computation_type]["lower"] = float(p10)
        interval_store[computation_type]["upper"] = float(p90)
        log_range[computation_type] = [float(to_log(y).min()), float(to_log(y).max())]

        best_log = np.full(len(group), np.nan)
        best_log[scored] = selected_log
        pred_mean = np.full(len(group), np.nan)
        pred_mean[scored] = mean_from_log_pred(best_log[scored], q)
        m_mean = report(y_s, pred_mean[scored])
        print(f"  {best} (mean mode) {fmt(m_mean)}")

        lo = from_log(best_log + p10)
        hi = from_log(best_log + p90)
        print(
            f"  P10-P90 interval: {np.mean(y_s < lo[scored]):.1%} below, "
            f"{np.mean(y_s > hi[scored]):.1%} above"
        )

        res_df = group.loc[scored, ["computation_type", "start_ms", TARGET]].copy()
        for kind in KINDS:
            res_df[f"pred_{kind}"] = from_log(oof[kind][scored])
        res_df["pred_nearest"] = from_log(oof["nearest"][scored])
        res_df["pred_blend"] = from_log(blend_log)
        res_df["predicted_seconds"] = from_log(best_log[scored])
        res_df["predicted_mean_seconds"] = pred_mean[scored]
        res_df["p10_seconds"] = lo[scored]
        res_df["p90_seconds"] = hi[scored]
        res_df["baseline_seconds"] = baseline[scored]
        all_results.append(res_df)

        evaluation[computation_type] = {
            "runs": len(group),
            "scored_runs": int(scored.sum()),
            "selected": chosen[computation_type],
            "metrics": metrics,
            "blend_metrics": blend_metrics,
            "blend_weights": blend_weights.tolist(),
            "selected_mean_mode": m_mean,
            "catboost_best_iterations": best_iters,
        }

        # Final model
        final_iters = None
        if best == "catboost" and not small:
            final_iters = int(np.median(best_iters) * 1.1)
        if use_blend:
            workload_model, _ = fit_candidate("ridge", computation_type, small, X, y)
            ml_model, _ = fit_candidate(
                best, computation_type, small, X, y, final_iters=final_iters
            )
            final_model = BlendModel(
                workload_model,
                ml_model,
                NearestRunModel().fit(X, to_log(y)),
                blend_weights,
            )
        else:
            final_model, _ = fit_candidate(
                best, computation_type, small, X, y, final_iters=final_iters
            )
        model_path = ARTIFACT_DIR / f"model_{computation_type}.joblib"
        joblib.dump(final_model, model_path)
        print(f"  saved {chosen[computation_type]} model: {model_path}")

    if not all_results:
        raise ValueError("No computation type had enough data.")

    results = pd.concat(all_results, ignore_index=True)

    overall = report(results[TARGET], results["predicted_seconds"])
    overall_base = report(results[TARGET], results["baseline_seconds"])
    print("\n--- Overall out-of-time (selected models) ---")
    print(f"  scored runs: {len(results)}")
    print(f"  model    {fmt(overall)}")
    print(f"  baseline {fmt(overall_base)}")

    metadata = {
        "target": TARGET,
        "target_unit": "seconds",
        "target_transform": TARGET_TRANSFORM,
        "features": feature_sets,
        "engineered_features": ENGINEERED,
        "computation_types": sorted(chosen),
        "selected_model": chosen,
        "log_residual_quantiles": residual_store,
        "log_interval_offsets": interval_store,
        "log_target_range": log_range,
        "cross_validation": {
            "method": "forward-chaining",
            "n_chunks": N_CHUNKS,
            "overall_model": overall,
            "overall_baseline": overall_base,
            "per_computation": evaluation,
        },
    }
    (ARTIFACT_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2))
    print(f"\nSaved: {ARTIFACT_DIR / 'metadata.json'}")


def main():
    train_models(refresh_data=True)


if __name__ == "__main__":
    main()
