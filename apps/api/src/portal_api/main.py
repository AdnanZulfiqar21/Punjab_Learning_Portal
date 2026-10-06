"""Application factory. Run locally:  uv run uvicorn portal_api.main:app --reload"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from portal_api import errors, observability
from portal_api.config import get_settings
from portal_api.modules.curriculum.router import router as curriculum_router
from portal_api.modules.system.router import router as system_router


def create_app() -> FastAPI:
    settings = get_settings()  # validates configuration; refuses unsafe production roles at startup
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = FastAPI(
        title="Punjab Learning Portal API",
        version="0.1.0",
        summary="Authoritative backend for student web, Android, iOS and staff admin.",
        docs_url="/docs" if settings.role.value in ("development", "test") else None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "Idempotency-Key", observability.HEADER],
        expose_headers=[observability.HEADER],
    )
    observability.install(app)
    errors.install(app)
    app.include_router(system_router)
    app.include_router(curriculum_router)
    return app


app = create_app()
