"""
AI Marketing OS — FastAPI Application Entry Point
"""
import logging
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from logging_config import (
    bind_request_id,
    configure_logging,
    get_request_id,
    new_request_id,
    reset_request_id,
)

logger = configure_logging()

from database.session import init_db
from api.routers import users, brands, products, plans, chat, scheduled, events, intelligence

# ── Init DB on startup ─────────────────────────────────────────────────────
try:
    init_db()
except Exception:
    logger.exception("database.initialization_failed")
    raise

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Marketing OS",
    description="نظام تشغيل تسويقي مبني على الذكاء الاصطناعي",
    version="1.1.3-integrated",
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    """Log every API request and return its trace ID to the browser."""

    request_id = new_request_id(request.headers.get("X-Request-ID"))
    token = bind_request_id(request_id)
    started_at = perf_counter()

    try:
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request.unhandled_error method=%s path=%s",
                request.method,
                request.url.path,
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "detail": "حدث خطأ داخلي. راجع سجل الخادم باستخدام رقم التتبع.",
                    "request_id": request_id,
                },
            )

        duration_ms = (perf_counter() - started_at) * 1000
        response.headers["X-Request-ID"] = request_id
        log_level = (
            logging.ERROR if response.status_code >= 500
            else logging.WARNING if response.status_code >= 400
            else logging.INFO
        )
        logger.log(
            log_level,
            "request.completed method=%s path=%s status=%s duration_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
    finally:
        reset_request_id(token)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Expose useful 422 details and log them under the same request ID."""

    errors = exc.errors()
    logger.warning(
        "request.validation_failed method=%s path=%s errors=%s",
        request.method,
        request.url.path,
        errors,
    )
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({
            "detail": errors,
            "message": "بيانات الطلب غير صالحة.",
            "request_id": get_request_id(),
        }),
    )

# CORS — allow the React dev server in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
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
app.include_router(scheduled.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(intelligence.router, prefix="/api/v1")


@app.on_event("shutdown")
def shutdown_intelligence() -> None:
    from services.brand_intelligence_service import close_memory_service

    close_memory_service()

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
