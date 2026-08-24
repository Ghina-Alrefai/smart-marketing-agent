from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.verify_release import (
    find_forbidden_release_entries,
    load_release_manifest,
    release_files,
    verify_manifest_checksums,
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_release_hygiene_rejects_runtime_files_and_allows_templates(tmp_path: Path) -> None:
    allowed = [tmp_path / ".env.example", tmp_path / "uploads" / ".gitkeep"]
    forbidden = [
        tmp_path / ".env",
        tmp_path / ".env.production",
        tmp_path / "marketing_os.db",
        tmp_path / "logs" / "app.log",
        tmp_path / "node_modules" / "package" / "index.js",
        tmp_path / "pkg" / "__pycache__" / "module.pyc",
        tmp_path / "uploads" / "generated.png",
    ]
    for path in allowed + forbidden:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test")

    errors = find_forbidden_release_entries(tmp_path)

    rendered = "\n".join(errors)
    assert ".env.example" not in rendered
    assert "uploads/.gitkeep" not in rendered
    assert "forbidden: .env (" in rendered
    assert "forbidden: .env.production (" in rendered
    assert "forbidden: marketing_os.db (" in rendered
    assert "forbidden: logs/ (" in rendered
    assert "forbidden: node_modules/ (" in rendered
    assert "forbidden: pkg/__pycache__/ (" in rendered
    assert "forbidden: uploads/generated.png (" in rendered


def test_manifest_validation_and_checksum_verification(tmp_path: Path) -> None:
    artifact = tmp_path / "artifacts" / "model.bin"
    artifact.parent.mkdir()
    artifact.write_bytes(b"model")
    manifest_text = (
        '{"release":"Example","version":"1.0.0","prepared_at":"2026-08-24",'
        '"verification":{},"sha256":{"model.bin":"'
        + _digest(b"model")
        + '"}}'
    )
    (tmp_path / "RELEASE_MANIFEST.json").write_text(manifest_text, encoding="utf-8")
    errors: list[str] = []

    manifest = load_release_manifest(tmp_path, errors)
    assert manifest is not None
    verified = verify_manifest_checksums(
        tmp_path,
        manifest,
        release_files(tmp_path),
        errors,
    )

    assert errors == []
    assert verified == [(artifact, _digest(b"model"))]


def test_manifest_reports_missing_ambiguous_and_mismatched_files(tmp_path: Path) -> None:
    first = tmp_path / "first" / "same.bin"
    second = tmp_path / "second" / "same.bin"
    mismatch = tmp_path / "artifact.bin"
    for path, contents in ((first, b"one"), (second, b"two"), (mismatch, b"actual")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    manifest = {
        "sha256": {
            "same.bin": _digest(b"one"),
            "missing.bin": _digest(b"missing"),
            "artifact.bin": _digest(b"expected"),
        }
    }
    errors: list[str] = []

    verified = verify_manifest_checksums(
        tmp_path,
        manifest,
        release_files(tmp_path),
        errors,
    )

    assert verified == []
    rendered = "\n".join(errors)
    assert "checksummed basename is ambiguous: same.bin" in rendered
    assert "checksummed file is missing: missing.bin" in rendered
    assert "artifact.bin expected" in rendered


def test_manifest_parser_rejects_invalid_json_and_duplicate_keys(tmp_path: Path) -> None:
    manifest_path = tmp_path / "RELEASE_MANIFEST.json"
    manifest_path.write_text("{not json", encoding="utf-8")
    errors: list[str] = []
    assert load_release_manifest(tmp_path, errors) is None
    assert "cannot parse" in errors[0]

    manifest_path.write_text(
        '{"release":"one","release":"two"}',
        encoding="utf-8",
    )
    errors = []
    assert load_release_manifest(tmp_path, errors) is None
    assert "duplicate JSON key: release" in errors[0]
