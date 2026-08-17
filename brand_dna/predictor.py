from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
import sklearn
from sklearn.metrics.pairwise import cosine_similarity

from .embeddings import encode_image, encode_text, load_image_encoder, load_text_encoder
from .explainability import aggregate_encoded_shap, explain_linear_model, sigmoid
from .features import (
    canonicalize_candidate,
    feature_value_map,
    prepare_base_features,
)
from .paths import project_root, resolve_project_path


def bundle_path(mode: str, root: Path | None = None) -> Path:
    root = root or project_root()
    if mode == "predesign":
        return root / "artifacts" / "performance_predesign.joblib"
    if mode == "multimodal":
        return root / "artifacts" / "performance_multimodal.joblib"
    raise ValueError("mode must be 'predesign' or 'multimodal'.")


def load_bundle(mode: str, root: Path | None = None) -> dict[str, Any]:
    path = bundle_path(mode, root)
    if not path.exists():
        raise FileNotFoundError(f"Model artifact is missing: {path}. Run `brand-dna train`.")
    bundle = joblib.load(path)
    artifact_version = bundle.get("created_with", {}).get("scikit_learn")
    if artifact_version != sklearn.__version__:
        raise RuntimeError(
            "scikit-learn version mismatch: artifact was created with "
            f"{artifact_version}, but runtime has {sklearn.__version__}. "
            "Install the exact version from requirements.txt or retrain locally."
        )
    return bundle


def predict_candidate(
    candidate: Mapping[str, Any],
    mode: str,
    root: Path | None = None,
    bundle: dict[str, Any] | None = None,
    precomputed_text_embedding: np.ndarray | None = None,
    precomputed_image_embedding: np.ndarray | None = None,
    text_model=None,
    image_model=None,
) -> dict[str, Any]:
    root = root or project_root()
    bundle = bundle or load_bundle(mode, root)

    if mode == "multimodal" and precomputed_image_embedding is None:
        image_path_value = str(candidate.get("image_path") or candidate.get("Image Path") or "").strip()
        if not image_path_value:
            raise ValueError(
                "Multimodal prediction requires an actual `image_path`. "
                "No mocked image similarity is allowed. Use mode='predesign' before the image exists."
            )

    canonical = canonicalize_candidate(candidate)
    base = prepare_base_features(canonical)
    caption = str(canonical.iloc[0]["caption"])
    text_vector = (
        np.asarray(precomputed_text_embedding, dtype=float)
        if precomputed_text_embedding is not None
        else encode_text(caption, model=text_model)
    )
    text_centroid = np.asarray(bundle["centroids"]["text_success_centroid"], dtype=float)
    text_similarity = float(
        cosine_similarity(text_vector.reshape(1, -1), text_centroid.reshape(1, -1))[0, 0]
    )
    similarities = {"text_similarity_to_success": text_similarity}
    base["text_similarity_to_success"] = text_similarity

    if mode == "multimodal":
        if precomputed_image_embedding is None:
            image_path_value = str(candidate.get("image_path") or candidate.get("Image Path"))
            image_path = resolve_project_path(image_path_value, root)
            image_vector = encode_image(image_path, model=image_model)
        else:
            image_vector = np.asarray(precomputed_image_embedding, dtype=float)
        image_centroid = np.asarray(
            bundle["centroids"]["image_success_centroid"], dtype=float
        )
        image_similarity = float(
            cosine_similarity(
                image_vector.reshape(1, -1), image_centroid.reshape(1, -1)
            )[0, 0]
        )
        similarities["image_similarity_to_success"] = image_similarity
        base["image_similarity_to_success"] = image_similarity

    transformed = np.asarray(bundle["preprocessor"].transform(base), dtype=float)
    probability = float(bundle["classifier"].predict_proba(transformed)[0, 1])
    shap_matrix, expected_log_odds = explain_linear_model(
        bundle["classifier"], bundle["background_transformed"], transformed
    )
    values = feature_value_map(canonical.iloc[0].to_dict(), similarities)
    attribution = aggregate_encoded_shap(
        shap_matrix[0],
        bundle["feature_names"],
        bundle["feature_groups"],
        bundle["group_order"],
        values,
    )
    decision = float(bundle["classifier"].decision_function(transformed)[0])
    residual = decision - (expected_log_odds + float(shap_matrix[0].sum()))

    raw_post_id = canonical.iloc[0].get("post_id")
    if raw_post_id is None or (isinstance(raw_post_id, float) and np.isnan(raw_post_id)):
        raw_post_id = candidate.get("id") or "candidate"

    return {
        "schema_version": "1.0",
        "post_id": str(raw_post_id),
        "model_version": bundle["model_version"],
        "brand_profile_version": bundle["brand_profile_version"],
        "mode": mode,
        "predicted_success_probability": round(probability, 10),
        "predicted_class_at_0_5": int(probability >= 0.5),
        "baseline_probability": round(sigmoid(expected_log_odds), 10),
        "shap_units": "log_odds",
        "shap_additivity_residual": round(float(residual), 12),
        "model_quality": bundle["cv_metrics"],
        "human_approval_required": True,
        "warnings": [
            "This is a model estimate, not a guarantee of Facebook performance.",
            "SHAP explains the trained model; it does not prove causality.",
        ],
        **attribution,
    }


def rank_candidates(
    candidates: list[Mapping[str, Any]],
    mode: str,
    root: Path | None = None,
) -> list[dict[str, Any]]:
    root = root or project_root()
    bundle = load_bundle(mode, root)
    # Load each encoder only once for the entire ranking batch.
    text_model = load_text_encoder()
    image_model = load_image_encoder() if mode == "multimodal" else None
    results = []
    for candidate in candidates:
        result = predict_candidate(
            candidate,
            mode,
            root=root,
            bundle=bundle,
            text_model=text_model,
            image_model=image_model,
        )
        result["candidate"] = dict(candidate)
        results.append(result)
    results.sort(key=lambda item: item["predicted_success_probability"], reverse=True)
    for index, result in enumerate(results, start=1):
        result["rank"] = index
    return results


def predict_historical_post(
    post_id: int,
    mode: str,
    root: Path | None = None,
) -> dict[str, Any]:
    import pandas as pd

    root = root or project_root()
    df = pd.read_csv(root / "data" / "processed" / "posts.csv").head(50)
    matches = df[df["Post ID"] == post_id]
    if matches.empty:
        raise ValueError(f"Post ID {post_id} was not found.")
    row_index = int(matches.index[0])
    text_embeddings = np.load(root / "artifacts" / "text_embeddings.npy")
    image_embeddings = np.load(root / "artifacts" / "image_embeddings.npy")
    candidate = matches.iloc[0].to_dict()
    return predict_candidate(
        candidate,
        mode,
        root=root,
        precomputed_text_embedding=text_embeddings[row_index],
        precomputed_image_embedding=image_embeddings[row_index]
        if mode == "multimodal"
        else None,
    )


def write_prediction(result: Any, output: str | Path | None) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text)
