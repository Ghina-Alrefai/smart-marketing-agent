from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brand_dna.constants import OUTCOME_OR_LEAKAGE_COLUMNS
from brand_dna.features import canonicalize_dataframe, prepare_base_features
from brand_dna.paths import project_root
from brand_dna.predictor import load_bundle, predict_candidate, predict_historical_post


def test_time_bucket_is_used() -> None:
    frame = pd.DataFrame([{"Caption": "test", "Time_Bucket": "Evening", "Day": "الخميس"}])
    canonical = canonicalize_dataframe(frame)
    features = prepare_base_features(canonical)
    assert canonical.iloc[0]["time_bucket"] == "Evening"
    assert features.iloc[0]["time_bucket"] == "Evening"
    assert features.iloc[0]["day"] == "الخميس"


def test_no_outcome_columns_enter_model() -> None:
    root = project_root()
    df = pd.read_csv(root / "data" / "processed" / "posts.csv").head(2)
    features = prepare_base_features(canonicalize_dataframe(df))
    assert OUTCOME_OR_LEAKAGE_COLUMNS.isdisjoint(features.columns)


def test_historical_prediction_and_shap_normalization() -> None:
    result = predict_historical_post(3, "multimodal")
    support = sum(item["success_support_0_1"] for item in result["feature_attributions"])
    importance = sum(item["importance_0_1"] for item in result["feature_attributions"])
    assert 0 <= result["predicted_success_probability"] <= 1
    assert abs(support - 1.0) < 1e-6
    assert abs(importance - 1.0) < 1e-6
    assert abs(result["shap_additivity_residual"]) < 1e-8


def test_multimodal_rejects_missing_image_before_embedding() -> None:
    bundle = load_bundle("multimodal")
    text_dim = bundle["centroids"]["text_success_centroid"].shape[0]
    with pytest.raises(ValueError, match="actual `image_path`"):
        predict_candidate(
            {"caption": "test", "time_bucket": "Evening", "day": "الخميس"},
            "multimodal",
            bundle=bundle,
            precomputed_text_embedding=np.zeros(text_dim),
        )
