"""Dependency-free release checks for the committee package."""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "main.py",
    "workflows/campaign_pipeline.py",
    "services/campaign_intelligence.py",
    "services/brand_intelligence_service.py",
    "brand_dna/generation.py",
    "adaptive_memory/services/memory_service.py",
    "artifacts/performance_predesign.joblib",
    "artifacts/performance_multimodal.joblib",
    "artifacts/model_card.json",
    "docs/full_workflow.html",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            errors.append(f"missing: {relative}")

    python_files = [
        path for path in ROOT.rglob("*.py")
        if ".venv" not in path.parts and "__pycache__" not in path.parts
    ]
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"syntax: {path.relative_to(ROOT)}: {exc}")

    card_path = ROOT / "artifacts" / "model_card.json"
    if card_path.exists():
        card = json.loads(card_path.read_text(encoding="utf-8"))
        if card.get("model_version") != "brand-dna-1.1.0":
            errors.append("unexpected model version")
        if card.get("training_rows") != 50:
            errors.append("unexpected packaged training row count")

    if errors:
        print("RELEASE CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("RELEASE CHECK PASSED")
    print(f"Python files parsed: {len(python_files)}")
    print(f"Predesign artifact SHA-256: {sha256(ROOT / 'artifacts/performance_predesign.joblib')}")
    print(f"Multimodal artifact SHA-256: {sha256(ROOT / 'artifacts/performance_multimodal.joblib')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
