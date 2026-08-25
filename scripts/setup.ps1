$ErrorActionPreference = "Stop"

# اسم مجلد البيئة الافتراضية: يُعاد استخدام الموجود (venv أو .venv) بدل إنشاء نسخة ثانية.
$VenvDir = if (Test-Path "venv") { "venv" } elseif (Test-Path ".venv") { ".venv" } else { ".venv" }

python scriptserify_release.py
if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment in $VenvDir ..." -ForegroundColor Cyan
    python -m venv $VenvDir
}
& ".\$VenvDir\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt

# لا تُتلف ملف إعدادات قائماً: .env يحوي مفاتيح حقيقية، و.env.example قيماً نموذجية.
if (Test-Path ".env") {
    Write-Host ".env already exists - keeping it (not overwritten)." -ForegroundColor Yellow
} else {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example - fill in the real values." -ForegroundColor Cyan
}

Push-Location frontend
npm ci
npm run build
Pop-Location
Write-Host "Setup complete. Ensure GOOGLE_API_KEY is set in .env, then run scripts/run.ps1" -ForegroundColor Green
