from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response as FastAPIResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.api import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import render_metrics
from app.db.bootstrap import bootstrap_database
from app.db.session import SessionLocal

settings = get_settings()
configure_logging(level=getattr(logging, settings.log_level.upper(), logging.INFO), log_format=settings.log_format)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version="2.0.0")


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; upgrade-insecure-requests"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list or ["*"])

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/metrics", include_in_schema=False)
def metrics() -> FastAPIResponse:
    output, content_type = render_metrics()
    return FastAPIResponse(content=output, media_type=content_type)


@app.on_event("startup")
def on_startup() -> None:
    Path(settings.artifacts_root).mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        bootstrap_database(db)
    finally:
        db.close()
    logger.info("API startup complete")

