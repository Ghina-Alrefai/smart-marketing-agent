#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
test -f .env || cp .env.example .env
(cd frontend && npm ci && npm run build)
python scripts/verify_release.py
echo "Setup complete. Put GOOGLE_API_KEY in .env, then run scripts/run.sh"
