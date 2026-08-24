"""
AI Marketing OS — FastAPI Application Entry Point
"""
import asyncio
import logging
from pathlib import Path
from time import perf_counter

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Match

from config import settings
from logging_config import (
    bind_request_id,
    configure_logging,
    get_request_id,
    new_request_id,
    reset_request_id,
)

logger = configure_logging()

from database.session import init_db, seed_admin
from api.routers import users, brands, products, plans, chat, scheduled, events, intelligence, auth, monitoring
from api.routers.auth import get_current_user


def _validate_security_settings() -> None:
    production = settings.APP_ENV.strip().lower() in {"production", "prod"}
    unsafe = []
    if settings.SECRET_KEY == "change-me-in-production":
        unsafe.append("SECRET_KEY")
    if settings.ADMIN_PASSWORD == "admin2026":
        unsafe.append("ADMIN_PASSWORD")
    if production and unsafe:
        raise RuntimeError(
            "Production startup refused: replace unsafe defaults for " + ", ".join(unsafe)
        )
    if unsafe:
        logger.warning("security.development_defaults_active settings=%s", ",".join(unsafe))

# ── Init DB on startup ─────────────────────────────────────────────────────
_validate_security_settings()
try:
    init_db()
except Exception:
    logger.exception("database.initialization_failed")
    raise
seed_admin()   # يهيّئ حساب المشرف الثابت إن لم يكن موجوداً

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Marketing OS",
    description="نظام تشغيل تسويقي مبني على الذكاء الاصطناعي",
    version="1.3.2-campaign-recovery",
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
        # Uploaded assets are deliberately restricted to decoded raster images.
        # Keep browsers from second-guessing their server-selected MIME type.
        response.headers["X-Content-Type-Options"] = "nosniff"
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
app.include_router(auth.router, prefix="/api/v1")
_authenticated = [Depends(get_current_user)]
_protected_api_routers = (
    users.router,
    brands.router,
    products.router,
    plans.router,
    chat.router,
    scheduled.router,
    events.router,
    intelligence.router,
)
for protected_router in _protected_api_routers:
    app.include_router(
        protected_router,
        prefix="/api/v1",
        dependencies=_authenticated,
    )
app.include_router(monitoring.router, prefix="/api/v1")
_all_api_routers = (auth.router, *_protected_api_routers, monitoring.router)


_API_FALLBACK_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


@app.api_route("/api", methods=_API_FALLBACK_METHODS, include_in_schema=False)
@app.api_route("/api/{api_path:path}", methods=_API_FALLBACK_METHODS, include_in_schema=False)
async def api_not_found(request: Request, api_path: str = "") -> JSONResponse:
    """Keep unknown/wrong-method API requests out of the React SPA fallback."""
    allowed_methods: set[str] = set()
    api_scope = dict(request.scope)
    if request.url.path.startswith("/api/v1"):
        api_scope["path"] = request.url.path[len("/api/v1"):] or "/"
        for router in _all_api_routers:
            for route in router.routes:
                match, _ = route.matches(api_scope)
                if match is Match.PARTIAL:
                    allowed_methods.update(getattr(route, "methods", set()) or set())

    if allowed_methods:
        allow = ", ".join(sorted(allowed_methods))
        return JSONResponse(
            status_code=405,
            content={"detail": "Method Not Allowed"},
            headers={"Allow": allow},
        )
    return JSONResponse(status_code=404, content={"detail": "API endpoint not found"})


def _preload_brand_dna_runtime() -> None:
    """Warm immutable model artifacts and encoders once for this API process."""
    from brand_dna.embeddings import load_image_encoder, load_text_encoder
    from brand_dna.paths import project_root
    from brand_dna.predictor import load_bundle

    root = project_root()
    load_bundle("predesign", root)
    load_bundle("multimodal", root)
    load_text_encoder()
    load_image_encoder()


@app.on_event("startup")
async def startup_brand_dna_runtime() -> None:
    if not settings.BRAND_DNA_PRELOAD_MODELS:
        logger.info("brand_dna.runtime_preload_disabled")
        return

    started_at = perf_counter()
    try:
        # Loading is blocking CPU/disk work. Keep it outside the event-loop
        # thread while still delaying readiness until the runtime is warm.
        await asyncio.to_thread(_preload_brand_dna_runtime)
    except Exception as exc:  # The API can still serve cold-start brands.
        logger.warning(
            "brand_dna.runtime_preload_failed error_type=%s error=%s",
            type(exc).__name__,
            str(exc)[:1000],
        )
        return

    logger.info(
        "brand_dna.runtime_preload_completed duration_ms=%.1f",
        (perf_counter() - started_at) * 1000,
    )


@app.on_event("startup")
async def startup_policy_review() -> None:
    from services.policy_review_scheduler import start_policy_review_scheduler

    start_policy_review_scheduler()


@app.on_event("shutdown")
async def shutdown_intelligence() -> None:
    from services.brand_intelligence_service import close_memory_service
    from services.policy_review_scheduler import stop_policy_review_scheduler

    await stop_policy_review_scheduler()
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
