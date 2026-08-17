$ErrorActionPreference = "Stop"
& .\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --host 127.0.0.1 --port 8000
