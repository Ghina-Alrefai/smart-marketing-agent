from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    # In the integrated application ``brand_dna`` is a top-level package next
    # to ``artifacts`` and ``data`` (not nested under a separate src/ folder).
    return Path(__file__).resolve().parents[1]


def resolve_project_path(value: str | Path, root: Path | None = None) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (root or project_root()) / path
