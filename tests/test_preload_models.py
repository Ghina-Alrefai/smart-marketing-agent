from __future__ import annotations

import runpy
from pathlib import Path

from brand_dna import embeddings, predictor


def test_direct_preload_script_entrypoint_imports_project_without_download(
    monkeypatch,
    capsys,
) -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "preload_models.py"
    loaded_bundles: list[tuple[str, Path]] = []
    loaded_encoders: list[str] = []

    monkeypatch.setattr(
        predictor,
        "load_bundle",
        lambda mode, bundle_root: loaded_bundles.append((mode, bundle_root)),
    )
    monkeypatch.setattr(
        embeddings,
        "load_text_encoder",
        lambda: loaded_encoders.append("text"),
    )
    monkeypatch.setattr(
        embeddings,
        "load_image_encoder",
        lambda: loaded_encoders.append("image"),
    )

    runpy.run_path(str(script), run_name="__main__")

    assert loaded_bundles == [("predesign", root), ("multimodal", root)]
    assert loaded_encoders == ["text", "image"]
    assert "All model dependencies are ready" in capsys.readouterr().out
