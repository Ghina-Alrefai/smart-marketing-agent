"""Dependency-free integrity and hygiene checks for a release package."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "main.py",
    "workflows/campaign_pipeline.py",
    "services/campaign_intelligence.py",
    "services/brand_intelligence_service.py",
    "brand_dna/generation.py",
    "adaptive_memory/services/memory_service.py",
    "adaptive_memory/engine/policy_reviewer.py",
    "services/policy_review_scheduler.py",
    "artifacts/performance_predesign.joblib",
    "artifacts/performance_multimodal.joblib",
    "artifacts/model_card.json",
    "docs/full_workflow.html",
    "docs/POLICY_REVIEW_AND_PROJECT_FLOW.md",
]

FORBIDDEN_DIRECTORY_REASONS = {
    "node_modules": "installed JavaScript dependencies",
    "__pycache__": "Python bytecode cache",
    ".pytest_cache": "pytest cache",
    ".mypy_cache": "mypy cache",
    ".ruff_cache": "Ruff cache",
    ".cache": "tool/runtime cache",
    ".vite": "Vite cache",
    "logs": "runtime logs",
}
DATABASE_FILE_RE = re.compile(
    r"\.(?:db|sqlite|sqlite3)(?:-(?:wal|shm|journal))?$",
    flags=re.IGNORECASE,
)
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _file_forbidden_reason(relative: Path) -> str | None:
    """Return why a regular file is release-only junk, if applicable."""
    parts = relative.parts
    name_lower = relative.name.lower()

    if parts and parts[0].lower() == "uploads":
        if relative.as_posix() != "uploads/.gitkeep":
            return "generated/uploaded runtime file"
        return None

    if name_lower == ".env" or (
        name_lower.startswith(".env.") and name_lower != ".env.example"
    ):
        return "environment/secrets file"
    if DATABASE_FILE_RE.search(name_lower):
        return "runtime database file"
    if name_lower.endswith(".log") or ".log." in name_lower:
        return "runtime log file"
    if name_lower.endswith((".pyc", ".pyo")):
        return "compiled Python bytecode"
    return None


def find_forbidden_release_entries(root: Path) -> list[str]:
    """Find secrets and generated/runtime material that must not ship."""
    errors: list[str] = []
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        current = Path(directory)
        kept_directories: list[str] = []

        for name in sorted(directory_names):
            path = current / name
            if path.is_symlink():
                errors.append(
                    f"forbidden: {_relative(path, root)} (symbolic-link directory)"
                )
                continue
            reason = FORBIDDEN_DIRECTORY_REASONS.get(name.lower())
            if reason is not None:
                errors.append(f"forbidden: {_relative(path, root)}/ ({reason})")
                continue
            kept_directories.append(name)
        directory_names[:] = kept_directories

        for name in sorted(file_names):
            path = current / name
            relative = path.relative_to(root)
            if path.is_symlink():
                errors.append(f"forbidden: {_relative(path, root)} (symbolic link)")
                continue
            reason = _file_forbidden_reason(relative)
            if reason is not None:
                errors.append(f"forbidden: {_relative(path, root)} ({reason})")

    return errors


def release_files(root: Path) -> list[Path]:
    """Inventory files while pruning directories already forbidden above."""
    files: list[Path] = []
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        current = Path(directory)
        directory_names[:] = [
            name
            for name in sorted(directory_names)
            if name.lower() not in FORBIDDEN_DIRECTORY_REASONS
            and not (current / name).is_symlink()
        ]
        for name in sorted(file_names):
            path = current / name
            if not path.is_symlink():
                files.append(path)
    return files


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_release_manifest(root: Path, errors: list[str]) -> dict[str, Any] | None:
    """Load and minimally validate the release manifest schema."""
    path = root / "RELEASE_MANIFEST.json"
    if not path.is_file():
        errors.append("manifest: missing RELEASE_MANIFEST.json")
        return None

    try:
        manifest = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"manifest: cannot parse RELEASE_MANIFEST.json: {exc}")
        return None

    if not isinstance(manifest, dict):
        errors.append("manifest: top-level value must be a JSON object")
        return None

    for field in ("release", "version", "prepared_at"):
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"manifest: {field!r} must be a non-empty string")

    prepared_at = manifest.get("prepared_at")
    if isinstance(prepared_at, str) and prepared_at.strip():
        try:
            date.fromisoformat(prepared_at)
        except ValueError:
            errors.append("manifest: 'prepared_at' must be an ISO date (YYYY-MM-DD)")

    verification = manifest.get("verification")
    if not isinstance(verification, dict):
        errors.append("manifest: 'verification' must be a JSON object")

    checksums = manifest.get("sha256")
    if not isinstance(checksums, dict) or not checksums:
        errors.append("manifest: 'sha256' must be a non-empty JSON object")

    return manifest


def _safe_manifest_key(key: str) -> PurePosixPath | None:
    if "\\" in key:
        return None
    path = PurePosixPath(key)
    if path.is_absolute() or not path.parts:
        return None
    if any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path


def _is_file_within_root(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return False
    return (
        path.is_file()
        and not path.is_symlink()
        and resolved.is_relative_to(root.resolve())
    )


def verify_manifest_checksums(
    root: Path,
    manifest: dict[str, Any],
    files: list[Path],
    errors: list[str],
) -> list[tuple[Path, str]]:
    """Resolve and verify every file named by the manifest's SHA-256 map."""
    checksums = manifest.get("sha256")
    if not isinstance(checksums, dict) or not checksums:
        return []

    by_basename: dict[str, list[Path]] = {}
    for path in files:
        by_basename.setdefault(path.name, []).append(path)

    verified: list[tuple[Path, str]] = []
    for key, expected in checksums.items():
        if not isinstance(key, str) or not key.strip():
            errors.append("manifest: every SHA-256 entry must have a non-empty string key")
            continue
        manifest_path = _safe_manifest_key(key)
        if manifest_path is None:
            errors.append(f"manifest: unsafe SHA-256 file path: {key!r}")
            continue
        if not isinstance(expected, str) or SHA256_RE.fullmatch(expected) is None:
            errors.append(f"manifest: invalid SHA-256 digest for {key}")
            expected_valid = False
        else:
            expected_valid = True

        if len(manifest_path.parts) > 1:
            candidate = root.joinpath(*manifest_path.parts)
            candidates = [candidate] if _is_file_within_root(candidate, root) else []
        else:
            candidates = by_basename.get(key, [])

        if not candidates:
            errors.append(f"manifest: checksummed file is missing: {key}")
            continue
        if len(candidates) > 1:
            locations = ", ".join(sorted(_relative(path, root) for path in candidates))
            errors.append(
                f"manifest: checksummed basename is ambiguous: {key} ({locations})"
            )
            continue
        if not expected_valid:
            continue

        candidate = candidates[0]
        try:
            actual = sha256(candidate)
        except OSError as exc:
            errors.append(f"checksum: cannot read {_relative(candidate, root)}: {exc}")
            continue
        if actual != expected.lower():
            errors.append(
                "checksum: "
                f"{_relative(candidate, root)} expected {expected.lower()}, got {actual}"
            )
            continue
        verified.append((candidate, actual))

    return verified


def run_checks(
    root: Path,
) -> tuple[list[str], list[Path], dict[str, Any] | None, list[tuple[Path, str]]]:
    errors = find_forbidden_release_entries(root)
    for relative in REQUIRED:
        if not (root / relative).is_file():
            errors.append(f"missing: {relative}")

    files = release_files(root)
    python_files = [path for path in files if path.suffix == ".py"]
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append(f"syntax: {_relative(path, root)}: {exc}")

    card_path = root / "artifacts" / "model_card.json"
    if card_path.exists():
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"model card: cannot parse artifacts/model_card.json: {exc}")
        else:
            if not isinstance(card, dict):
                errors.append("model card: top-level value must be a JSON object")
            else:
                if card.get("model_version") != "brand-dna-1.1.0":
                    errors.append("unexpected model version")
                if card.get("training_rows") != 50:
                    errors.append("unexpected packaged training row count")

    manifest_errors: list[str] = []
    manifest = load_release_manifest(root, manifest_errors)
    errors.extend(manifest_errors)
    verified: list[tuple[Path, str]] = []
    if manifest is not None:
        verified = verify_manifest_checksums(root, manifest, files, errors)

    return sorted(set(errors)), python_files, manifest, verified


def main() -> int:
    errors, python_files, manifest, verified = run_checks(ROOT)
    if errors:
        print("RELEASE CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    assert manifest is not None
    print("RELEASE CHECK PASSED")
    print(f"Manifest: {manifest['release']} ({manifest['version']})")
    print(f"Manifest checksums verified: {len(verified)}")
    print(f"Python files parsed: {len(python_files)}")
    for name in ("performance_predesign.joblib", "performance_multimodal.joblib"):
        match = next((digest for path, digest in verified if path.name == name), None)
        if match is not None:
            label = "Predesign" if name.startswith("performance_predesign") else "Multimodal"
            print(f"{label} artifact SHA-256: {match}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
