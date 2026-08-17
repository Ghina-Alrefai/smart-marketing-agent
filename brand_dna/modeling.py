from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .constants import (
    CATEGORICAL_FEATURES,
    FEATURE_GROUP_ORDER_MULTIMODAL,
    FEATURE_GROUP_ORDER_PREDESIGN,
    IMAGE_MODEL_NAME,
    LOGISTIC_C,
    MODEL_VERSION,
    N_SPLITS,
    ONE_HOT_MIN_FREQUENCY,
    RANDOM_STATE,
    TARGET_COLUMN,
    TEXT_MODEL_NAME,
)
from .embeddings import (
    fold_similarity_features,
    leave_one_out_success_similarity,
    success_centroid,
    validate_embeddings,
)
from .explainability import (
    aggregate_encoded_shap,
    explain_linear_model,
    sigmoid,
    summarize_evidence,
    write_jsonl,
)
from .features import (
    canonicalize_dataframe,
    feature_value_map,
    group_for_source_feature,
    prepare_base_features,
)
from .profile import save_stable_brand_profile


def _add_similarity_columns(frame: pd.DataFrame, values: dict[str, np.ndarray]) -> pd.DataFrame:
    output = frame.copy()
    for column, vector in values.items():
        output[column] = np.asarray(vector, dtype=float)
    return output


def _build_preprocessor(frame: pd.DataFrame) -> tuple[ColumnTransformer, list[str], list[str]]:
    categorical = [column for column in CATEGORICAL_FEATURES if column in frame.columns]
    numeric = [column for column in frame.columns if column not in categorical]
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "one_hot",
                            OneHotEncoder(
                                handle_unknown="ignore",
                                min_frequency=ONE_HOT_MIN_FREQUENCY,
                                sparse_output=False,
                            ),
                        ),
                    ]
                ),
                categorical,
            ),
            (
                "num",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric,
            ),
        ],
        sparse_threshold=0,
        verbose_feature_names_out=True,
    )
    return preprocessor, categorical, numeric


def _classifier() -> LogisticRegression:
    return LogisticRegression(
        C=LOGISTIC_C,
        solver="liblinear",
        class_weight="balanced",
        max_iter=5000,
        random_state=RANDOM_STATE,
    )


def _encoded_feature_metadata(
    preprocessor: ColumnTransformer,
    categorical_columns: list[str],
    numeric_columns: list[str],
) -> tuple[list[str], list[str], list[str]]:
    feature_names = list(preprocessor.get_feature_names_out())
    source_columns: list[str] = []
    groups: list[str] = []
    categorical_sorted = sorted(categorical_columns, key=len, reverse=True)

    for name in feature_names:
        if name.startswith("cat__"):
            remainder = name[len("cat__") :]
            source = next(
                (
                    column
                    for column in categorical_sorted
                    if remainder == column or remainder.startswith(column + "_")
                ),
                remainder.split("_", 1)[0],
            )
        elif name.startswith("num__"):
            source = name[len("num__") :]
        else:
            source = name
        source_columns.append(source)
        groups.append(group_for_source_feature(source))
    return feature_names, source_columns, groups


def _metrics(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, float]:
    predictions = (probabilities >= 0.5).astype(int)
    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "log_loss": float(log_loss(y_true, probabilities)),
    }


def evaluate_oof(
    df: pd.DataFrame,
    text_embeddings: np.ndarray,
    image_embeddings: np.ndarray,
    mode: str,
    brand_profile_version: str,
    create_evidence: bool = False,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]]]:
    canonical = canonicalize_dataframe(df)
    base = prepare_base_features(canonical)
    y = pd.to_numeric(df[TARGET_COLUMN], errors="raise").astype(int).to_numpy()
    cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    probabilities = np.zeros(len(df), dtype=float)
    fold_ids = np.zeros(len(df), dtype=int)
    evidence_records: list[dict[str, Any]] = []
    fold_metrics: list[dict[str, float]] = []
    group_order = (
        FEATURE_GROUP_ORDER_MULTIMODAL
        if mode == "multimodal"
        else FEATURE_GROUP_ORDER_PREDESIGN
    )

    for fold_number, (train_indices, validation_indices) in enumerate(cv.split(base, y), start=1):
        train_similarity, validation_similarity, _ = fold_similarity_features(
            text_embeddings,
            image_embeddings,
            y,
            train_indices,
            validation_indices,
            mode,
        )
        X_train = _add_similarity_columns(base.iloc[train_indices], train_similarity)
        X_validation = _add_similarity_columns(
            base.iloc[validation_indices], validation_similarity
        )
        preprocessor, categorical_columns, numeric_columns = _build_preprocessor(X_train)
        X_train_transformed = np.asarray(preprocessor.fit_transform(X_train), dtype=float)
        X_validation_transformed = np.asarray(
            preprocessor.transform(X_validation), dtype=float
        )
        classifier = _classifier()
        classifier.fit(X_train_transformed, y[train_indices])
        fold_probabilities = classifier.predict_proba(X_validation_transformed)[:, 1]
        probabilities[validation_indices] = fold_probabilities
        fold_ids[validation_indices] = fold_number
        fold_metrics.append(_metrics(y[validation_indices], fold_probabilities))

        if create_evidence:
            feature_names, _, feature_groups = _encoded_feature_metadata(
                preprocessor, categorical_columns, numeric_columns
            )
            shap_matrix, expected_log_odds = explain_linear_model(
                classifier, X_train_transformed, X_validation_transformed
            )
            decisions = classifier.decision_function(X_validation_transformed)
            residuals = decisions - (expected_log_odds + shap_matrix.sum(axis=1))
            for local_index, row_index in enumerate(validation_indices):
                similarities = {
                    column: float(values[local_index])
                    for column, values in validation_similarity.items()
                }
                value_map = feature_value_map(
                    canonical.iloc[row_index].to_dict(), similarities
                )
                attribution = aggregate_encoded_shap(
                    shap_matrix[local_index],
                    feature_names,
                    feature_groups,
                    group_order,
                    value_map,
                )
                actual_success = bool(y[row_index] == 1)
                evidence_records.append(
                    {
                        "schema_version": "1.0",
                        "evidence_type": "post_success_feature_attribution"
                        if actual_success
                        else "post_failure_feature_attribution",
                        "source": "brand_dna",
                        "post_id": str(canonical.iloc[row_index].get("post_id")),
                        "campaign_id": None,
                        "brand_profile_version": brand_profile_version,
                        "model_version": f"{MODEL_VERSION}-{mode}-oof",
                        "explainer_version": "shap-linear-independent-oof-v1",
                        "fold": fold_number,
                        "actual_success": actual_success,
                        "actual_performance": {
                            "relative_performance_index": _finite_or_none(
                                canonical.iloc[row_index].get(
                                    "relative_performance_index"
                                )
                            ),
                            "weighted_engagement": _finite_or_none(
                                canonical.iloc[row_index].get("weighted_engagement")
                            ),
                        },
                        "predicted_success_probability": round(
                            float(fold_probabilities[local_index]), 10
                        ),
                        "baseline_probability": round(sigmoid(expected_log_odds), 10),
                        "shap_units": "log_odds",
                        "shap_additivity_residual": round(
                            float(residuals[local_index]), 12
                        ),
                        "human_approval_required": True,
                        **attribution,
                    }
                )

    overall = _metrics(y, probabilities)
    overall["fold_metric_mean"] = {
        key: float(np.mean([metric[key] for metric in fold_metrics]))
        for key in fold_metrics[0]
    }
    overall["fold_metric_std"] = {
        key: float(np.std([metric[key] for metric in fold_metrics], ddof=0))
        for key in fold_metrics[0]
    }
    overall["probability_min"] = float(probabilities.min())
    overall["probability_max"] = float(probabilities.max())
    if create_evidence:
        for record in evidence_records:
            record["model_quality"] = overall

    predictions_frame = pd.DataFrame(
        {
            "post_id": canonical["post_id"].astype(str),
            "actual_success": y,
            "predicted_success_probability": probabilities,
            "predicted_class_at_0_5": (probabilities >= 0.5).astype(int),
            "fold": fold_ids,
            "mode": mode,
        }
    )
    return overall, predictions_frame, evidence_records


def fit_final_bundle(
    df: pd.DataFrame,
    text_embeddings: np.ndarray,
    image_embeddings: np.ndarray,
    mode: str,
    metrics: dict[str, Any],
    brand_profile_version: str,
    data_hash: str,
) -> dict[str, Any]:
    canonical = canonicalize_dataframe(df)
    base = prepare_base_features(canonical)
    y = pd.to_numeric(df[TARGET_COLUMN], errors="raise").astype(int).to_numpy()
    all_indices = np.arange(len(df))
    text_centroid = success_centroid(text_embeddings, y, all_indices)
    similarities = {
        "text_similarity_to_success": leave_one_out_success_similarity(
            text_embeddings, y, all_indices
        )
    }
    centroids = {"text_success_centroid": text_centroid}
    if mode == "multimodal":
        image_centroid = success_centroid(image_embeddings, y, all_indices)
        similarities["image_similarity_to_success"] = leave_one_out_success_similarity(
            image_embeddings, y, all_indices
        )
        centroids["image_success_centroid"] = image_centroid
    elif mode != "predesign":
        raise ValueError("mode must be 'predesign' or 'multimodal'.")

    X = _add_similarity_columns(base, similarities)
    preprocessor, categorical_columns, numeric_columns = _build_preprocessor(X)
    X_transformed = np.asarray(preprocessor.fit_transform(X), dtype=float)
    classifier = _classifier()
    classifier.fit(X_transformed, y)
    feature_names, source_columns, feature_groups = _encoded_feature_metadata(
        preprocessor, categorical_columns, numeric_columns
    )
    group_order = (
        FEATURE_GROUP_ORDER_MULTIMODAL
        if mode == "multimodal"
        else FEATURE_GROUP_ORDER_PREDESIGN
    )
    return {
        "artifact_schema_version": "2.0",
        "model_version": f"{MODEL_VERSION}-{mode}",
        "mode": mode,
        "created_with": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "brand_profile_version": brand_profile_version,
        "training_data_hash": data_hash,
        "target": {
            "name": TARGET_COLUMN,
            "positive_class": 1,
            "definition": "Weighted engagement at or above the historical median.",
        },
        "text_embedding_model": TEXT_MODEL_NAME,
        "image_embedding_model": IMAGE_MODEL_NAME if mode == "multimodal" else None,
        "preprocessor": preprocessor,
        "classifier": classifier,
        "background_transformed": X_transformed,
        "feature_names": feature_names,
        "source_columns": source_columns,
        "feature_groups": feature_groups,
        "group_order": group_order,
        "centroids": centroids,
        "cv_metrics": metrics,
        "human_approval_required": True,
        "limitations": [
            "Only 50 historical posts are available.",
            "Attributions explain the model and are not causal effects.",
            "Do not create an Adaptive Memory policy from one post; aggregate repeated evidence.",
        ],
    }


def train_project(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    data_path = root / "data" / "processed" / "posts.csv"
    text_path = root / "artifacts" / "text_embeddings.npy"
    image_path = root / "artifacts" / "image_embeddings.npy"
    df = pd.read_csv(data_path).head(50).copy()
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Missing target column: {TARGET_COLUMN}")
    y = pd.to_numeric(df[TARGET_COLUMN], errors="raise").astype(int)
    if set(y.unique()) != {0, 1}:
        raise ValueError("Performance_Class must contain both 0 and 1.")

    text_embeddings = np.load(text_path)
    image_embeddings = np.load(image_path)
    validate_embeddings(text_embeddings, image_embeddings, len(df))

    artifacts = root / "artifacts"
    evaluation = root / "outputs" / "evaluation"
    memory_output = root / "outputs" / "adaptive_memory"
    artifacts.mkdir(parents=True, exist_ok=True)
    evaluation.mkdir(parents=True, exist_ok=True)
    memory_output.mkdir(parents=True, exist_ok=True)

    profile = save_stable_brand_profile(df, artifacts / "brand_profile.json")
    profile_version = profile["brand_profile_version"]
    data_hash = _hash_training_inputs(data_path, text_path, image_path)

    pre_metrics, pre_predictions, _ = evaluate_oof(
        df,
        text_embeddings,
        image_embeddings,
        mode="predesign",
        brand_profile_version=profile_version,
        create_evidence=False,
    )
    multi_metrics, multi_predictions, records = evaluate_oof(
        df,
        text_embeddings,
        image_embeddings,
        mode="multimodal",
        brand_profile_version=profile_version,
        create_evidence=True,
    )

    pre_bundle = fit_final_bundle(
        df,
        text_embeddings,
        image_embeddings,
        "predesign",
        pre_metrics,
        profile_version,
        data_hash,
    )
    multi_bundle = fit_final_bundle(
        df,
        text_embeddings,
        image_embeddings,
        "multimodal",
        multi_metrics,
        profile_version,
        data_hash,
    )
    joblib.dump(pre_bundle, artifacts / "performance_predesign.joblib")
    joblib.dump(multi_bundle, artifacts / "performance_multimodal.joblib")

    pre_predictions.to_csv(evaluation / "oof_predictions_predesign.csv", index=False)
    multi_predictions.to_csv(evaluation / "oof_predictions_multimodal.csv", index=False)
    write_jsonl(records, memory_output / "all_oof_attributions.jsonl")
    success_records = [record for record in records if record["actual_success"]]
    write_jsonl(success_records, memory_output / "success_evidence.jsonl")
    summary = summarize_evidence(records)
    (memory_output / "success_feature_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    model_card = {
        "model_version": MODEL_VERSION,
        "training_rows": len(df),
        "class_distribution": {
            "success": int((y == 1).sum()),
            "failure": int((y == 0).sum()),
        },
        "leakage_controls": [
            "Fold-specific success centroids during cross-validation.",
            "Leave-one-out success centroids for successful training rows.",
            "Out-of-fold SHAP explanations for historical evidence.",
            "No post-publication engagement field enters the predictor.",
        ],
        "predesign_cv_metrics": pre_metrics,
        "multimodal_cv_metrics": multi_metrics,
        "adaptive_memory_success_evidence_count": len(success_records),
        "brand_profile_version": profile_version,
        "training_data_hash": data_hash,
        "recommended_minimum_policy_support": 5,
        "warning": (
            "The dataset is small. Use the probability as a ranking signal and keep human approval; "
            "do not interpret SHAP as causality."
        ),
    }
    (artifacts / "model_card.json").write_text(
        json.dumps(model_card, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return model_card


def _hash_training_inputs(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def _finite_or_none(value: Any) -> float | int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    if number.is_integer():
        return int(number)
    return number
