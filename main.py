"""
AI Marketing OS — FastAPI Application Entry Point
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from config import settings
from database.session import init_db
from api.routers import users, brands, products, plans, chat

# ── Init DB on startup ─────────────────────────────────────────────────────
init_db()

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Marketing OS",
    description="نظام تشغيل تسويقي مبني على الذكاء الاصطناعي",
    version="1.0.0",
)

# CORS — allow the React dev server in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files
uploads_path = Path(settings.UPLOAD_DIR)
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(users.router, prefix="/api/v1")
app.include_router(brands.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")

# ── Serve React frontend build ─────────────────────────────────────────────
_frontend_dist = Path(__file__).parent / "frontend" / "dist"

if _frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(_frontend_dist / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_react(full_path: str):
        file_path = _frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_frontend_dist / "index.html")
else:
    @app.get("/")
    def health_check():
        return {"status": "ok", "app": "AI Marketing OS"}
