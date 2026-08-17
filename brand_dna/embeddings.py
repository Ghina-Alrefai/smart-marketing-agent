from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .constants import IMAGE_MODEL_NAME, TEXT_MODEL_NAME


def validate_embeddings(
    text_embeddings: np.ndarray,
    image_embeddings: np.ndarray,
    expected_rows: int,
) -> None:
    if text_embeddings.ndim != 2 or len(text_embeddings) != expected_rows:
        raise ValueError(
            f"Text embeddings have shape {text_embeddings.shape}; expected ({expected_rows}, d)."
        )
    if image_embeddings.ndim != 2 or len(image_embeddings) != expected_rows:
        raise ValueError(
            f"Image embeddings have shape {image_embeddings.shape}; expected ({expected_rows}, d)."
        )
    if not np.isfinite(text_embeddings).all() or not np.isfinite(image_embeddings).all():
        raise ValueError("Embedding arrays contain NaN or infinite values.")


def similarity_to_centroid(vectors: np.ndarray, centroid: np.ndarray) -> np.ndarray:
    return cosine_similarity(vectors, centroid.reshape(1, -1)).reshape(-1)


def success_centroid(embeddings: np.ndarray, y: np.ndarray, indices: np.ndarray) -> np.ndarray:
    success_indices = indices[y[indices] == 1]
    if len(success_indices) == 0:
        raise ValueError("A training fold contains no successful posts; cannot build centroid.")
    return embeddings[success_indices].mean(axis=0)


def leave_one_out_success_similarity(
    embeddings: np.ndarray,
    y: np.ndarray,
    indices: np.ndarray,
) -> np.ndarray:
    success_indices = indices[y[indices] == 1]
    if len(success_indices) < 2:
        raise ValueError("At least two successful training posts are required.")
    full_centroid = embeddings[success_indices].mean(axis=0)
    values: list[float] = []
    for row_index in indices:
        if y[row_index] == 1:
            other_successes = success_indices[success_indices != row_index]
            centroid = embeddings[other_successes].mean(axis=0)
        else:
            centroid = full_centroid
        value = cosine_similarity(
            embeddings[row_index].reshape(1, -1), centroid.reshape(1, -1)
        )[0, 0]
        values.append(float(value))
    return np.asarray(values, dtype=float)


def fold_similarity_features(
    text_embeddings: np.ndarray,
    image_embeddings: np.ndarray,
    y: np.ndarray,
    train_indices: np.ndarray,
    validation_indices: np.ndarray,
    mode: str,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, np.ndarray]]:
    text_centroid = success_centroid(text_embeddings, y, train_indices)
    train_features = {
        "text_similarity_to_success": leave_one_out_success_similarity(
            text_embeddings, y, train_indices
        )
    }
    validation_features = {
        "text_similarity_to_success": similarity_to_centroid(
            text_embeddings[validation_indices], text_centroid
        )
    }
    centroids = {"text_success_centroid": text_centroid}

    if mode == "multimodal":
        image_centroid = success_centroid(image_embeddings, y, train_indices)
        train_features["image_similarity_to_success"] = leave_one_out_success_similarity(
            image_embeddings, y, train_indices
        )
        validation_features["image_similarity_to_success"] = similarity_to_centroid(
            image_embeddings[validation_indices], image_centroid
        )
        centroids["image_success_centroid"] = image_centroid
    elif mode != "predesign":
        raise ValueError("mode must be 'predesign' or 'multimodal'.")

    return train_features, validation_features, centroids


def load_text_encoder():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is required for new-caption prediction. "
            "Install requirements.txt first."
        ) from exc
    return SentenceTransformer(TEXT_MODEL_NAME)


def load_image_encoder():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is required for image prediction. "
            "Install requirements.txt first."
        ) from exc
    return SentenceTransformer(IMAGE_MODEL_NAME)


def encode_text(text: str, model=None) -> np.ndarray:
    model = model or load_text_encoder()
    result = model.encode([text], show_progress_bar=False)
    return np.asarray(result[0], dtype=float)


def encode_image(image_path: str | Path, model=None) -> np.ndarray:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image does not exist: {path}")
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required to read images.") from exc
    model = model or load_image_encoder()
    with Image.open(path) as image:
        image = image.convert("RGB")
        result = model.encode(image, show_progress_bar=False)
    return np.asarray(result, dtype=float)


def rebuild_embeddings(
    captions: Iterable[str],
    image_paths: Iterable[str | Path],
    text_output: str | Path,
    image_output: str | Path,
) -> tuple[np.ndarray, np.ndarray]:
    text_model = load_text_encoder()
    image_model = load_image_encoder()
    captions_list = list(captions)
    text_embeddings = np.asarray(
        text_model.encode(captions_list, show_progress_bar=True), dtype=float
    )
    image_vectors = []
    for path in image_paths:
        image_vectors.append(encode_image(path, model=image_model))
    image_embeddings = np.asarray(image_vectors, dtype=float)
    np.save(text_output, text_embeddings)
    np.save(image_output, image_embeddings)
    return text_embeddings, image_embeddings
