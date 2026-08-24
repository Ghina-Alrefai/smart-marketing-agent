"""Safe, isolated defaults applied before test modules import application config."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


_TEST_ROOT = Path(tempfile.gettempdir()) / f"smartsocial-tests-{os.getpid()}"
_TEST_ROOT.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-only-session-signing-key-32-bytes-minimum")
os.environ.setdefault("ADMIN_PASSWORD", "test-only-admin-password")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_ROOT / 'application.db'}")
os.environ.setdefault("ADAPTIVE_MEMORY_DB", str(_TEST_ROOT / "adaptive-memory.db"))
os.environ.setdefault("UPLOAD_DIR", str(_TEST_ROOT / "uploads"))
os.environ.setdefault("LOG_TO_FILE", "false")
os.environ.setdefault("BRAND_DNA_PRELOAD_MODELS", "false")
os.environ.setdefault("POLICY_REVIEW_ENABLED", "false")
