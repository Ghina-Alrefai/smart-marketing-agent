$ErrorActionPreference = "Stop"

$VenvDir = if (Test-Path "venv") { "venv" } elseif (Test-Path ".venv") { ".venv" } else { $null }
if (-not $VenvDir) {
    Write-Error "No virtual environment found. Run scripts\setup.ps1 first."
    exit 1
}
& ".\$VenvDir\Scripts\Activate.ps1"
uvicorn main:app --reload --host 127.0.0.1 --port 8000
