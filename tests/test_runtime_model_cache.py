from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from brand_dna import embeddings, predictor
from brand_dna.constants import IMAGE_MODEL_NAME, TEXT_MODEL_NAME


@pytest.fixture(autouse=True)
def _empty_runtime_caches():
    embeddings.clear_encoder_cache()
    predictor.clear_bundle_cache()
    yield
    embeddings.clear_encoder_cache()
    predictor.clear_bundle_cache()


def test_encoders_are_loaded_once_and_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    constructed: list[str] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name: str):
            constructed.append(model_name)

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )

    first_text = embeddings.load_text_encoder()
    second_text = embeddings.load_text_encoder()
    first_image = embeddings.load_image_encoder()
    second_image = embeddings.load_image_encoder()

    assert first_text is second_text
    assert first_image is second_image
    assert constructed == [TEXT_MODEL_NAME, IMAGE_MODEL_NAME]


def test_simultaneous_requests_construct_only_one_encoder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    construction_count = 0

    class SlowFakeSentenceTransformer:
        def __init__(self, _model_name: str):
            nonlocal construction_count
            construction_count += 1
            time.sleep(0.02)

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=SlowFakeSentenceTransformer),
    )

    with ThreadPoolExecutor(max_workers=8) as pool:
        encoders = list(pool.map(lambda _: embeddings.load_text_encoder(), range(16)))

    assert construction_count == 1
    assert all(encoder is encoders[0] for encoder in encoders)


def _artifact(root: Path, mode: str = "predesign") -> Path:
    path = predictor.bundle_path(mode, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"artifact-v1")
    return path


def _fake_bundle(marker: int) -> dict:
    return {
        "created_with": {"scikit_learn": predictor.sklearn.__version__},
        "marker": marker,
    }


def test_unchanged_joblib_bundle_is_loaded_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _artifact(tmp_path)
    load_count = 0

    def fake_load(_path: Path) -> dict:
        nonlocal load_count
        load_count += 1
        return _fake_bundle(load_count)

    monkeypatch.setattr(predictor.joblib, "load", fake_load)

    first = predictor.load_bundle("predesign", tmp_path)
    second = predictor.load_bundle("predesign", tmp_path)

    assert first is second
    assert load_count == 1


def test_changed_joblib_artifact_refreshes_cached_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _artifact(tmp_path)
    load_count = 0

    def fake_load(_path: Path) -> dict:
        nonlocal load_count
        load_count += 1
        return _fake_bundle(load_count)

    monkeypatch.setattr(predictor.joblib, "load", fake_load)

    first = predictor.load_bundle("predesign", tmp_path)
    artifact.write_bytes(b"artifact-v2-with-different-size")
    second = predictor.load_bundle("predesign", tmp_path)

    assert first is not second
    assert first["marker"] == 1
    assert second["marker"] == 2
    assert load_count == 2


def test_explicit_cache_clear_forces_bundle_reload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _artifact(tmp_path)
    load_count = 0

    def fake_load(_path: Path) -> dict:
        nonlocal load_count
        load_count += 1
        return _fake_bundle(load_count)

    monkeypatch.setattr(predictor.joblib, "load", fake_load)

    first = predictor.load_bundle("predesign", tmp_path)
    predictor.clear_bundle_cache("predesign", tmp_path)
    second = predictor.load_bundle("predesign", tmp_path)

    assert first is not second
    assert load_count == 2


def test_simultaneous_requests_load_joblib_bundle_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _artifact(tmp_path)
    load_count = 0

    def slow_fake_load(_path: Path) -> dict:
        nonlocal load_count
        load_count += 1
        time.sleep(0.02)
        return _fake_bundle(load_count)

    monkeypatch.setattr(predictor.joblib, "load", slow_fake_load)

    with ThreadPoolExecutor(max_workers=8) as pool:
        bundles = list(
            pool.map(
                lambda _: predictor.load_bundle("predesign", tmp_path),
                range(16),
            )
        )

    assert load_count == 1
    assert all(bundle is bundles[0] for bundle in bundles)


def test_repeated_ranking_batches_reuse_runtime_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _artifact(tmp_path)
    joblib_load_count = 0
    encoder_construction_count = 0

    def fake_load(_path: Path) -> dict:
        nonlocal joblib_load_count
        joblib_load_count += 1
        return _fake_bundle(joblib_load_count)

    class FakeSentenceTransformer:
        def __init__(self, _model_name: str):
            nonlocal encoder_construction_count
            encoder_construction_count += 1

    def fake_predict(candidate, mode, **_kwargs):
        return {
            "post_id": candidate["id"],
            "predicted_success_probability": candidate["score"],
            "mode": mode,
        }

    monkeypatch.setattr(predictor.joblib, "load", fake_load)
    monkeypatch.setattr(predictor, "predict_candidate", fake_predict)
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    candidates = [
        {"id": "a", "score": 0.7},
        {"id": "b", "score": 0.8},
        {"id": "c", "score": 0.6},
    ]

    first = predictor.rank_candidates(candidates, "predesign", root=tmp_path)
    second = predictor.rank_candidates(candidates, "predesign", root=tmp_path)

    assert [item["post_id"] for item in first] == ["b", "a", "c"]
    assert [item["post_id"] for item in second] == ["b", "a", "c"]
    assert joblib_load_count == 1
    assert encoder_construction_count == 1
