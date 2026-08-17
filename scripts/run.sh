#!/usr/bin/env bash
set -euo pipefail
. .venv/bin/activate
exec uvicorn main:app --reload --host 127.0.0.1 --port 8000
