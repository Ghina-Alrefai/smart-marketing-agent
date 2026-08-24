from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_committee_demo_direct_entrypoint_is_idempotent(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "committee_demo.py"
    database = tmp_path / "demo.db"
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{database}",
            "ADAPTIVE_MEMORY_DB": str(tmp_path / "memory.db"),
        }
    )

    first = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    second = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert json.loads(first.stdout)["reused_existing_demo"] is False
    assert json.loads(second.stdout)["reused_existing_demo"] is True
    with sqlite3.connect(database) as connection:
        plans = connection.execute("SELECT COUNT(*) FROM content_plans").fetchone()[0]
        posts = connection.execute("SELECT COUNT(*) FROM generated_posts").fetchone()[0]
    assert plans == 1
    assert posts == 1
