$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env -ErrorAction SilentlyContinue
Push-Location frontend
npm ci
npm run build
Pop-Location
python scripts\verify_release.py
Write-Host "Setup complete. Put GOOGLE_API_KEY in .env, then run scripts\run.ps1" -ForegroundColor Green
