"""Application factory. Run locally:  uv run uvicorn portal_api.main:app --reload"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from portal_api import errors, observability
from portal_api.config import get_settings
from portal_api.modules.access import trial_devices
from portal_api.modules.access.router import router as access_router
from portal_api.modules.assessment.router import router as assessment_router
from portal_api.modules.audit.router import router as audit_router
from portal_api.modules.content import router as content
from portal_api.modules.curriculum.router import router as curriculum_router
from portal_api.modules.help.router import router as help_router
from portal_api.modules.identity import dev_auth
from portal_api.modules.identity.router import router as identity_router
from portal_api.modules.notifications.router import router as notifications_router
from portal_api.modules.support.router import router as support_router
from portal_api.modules.system.router import router as system_router
from portal_api.modules.written.review_router import router as written_review_router
from portal_api.modules.written.router import router as written_router


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
        allow_headers=[
            "Content-Type",
            "Authorization",
            "Idempotency-Key",
            "X-Portal-Client",
            "X-Portal-Install",
            observability.HEADER,
        ],
        expose_headers=[observability.HEADER],
    )
    observability.install(app)

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # P18.S2.T1 (HEADERS-01): JSON API responses are never framed, sniffed or used as documents. The
        # development-only /docs page needs its own scripts, so it keeps the browser defaults.
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if not request.url.path.startswith(("/docs", "/openapi.json")):
            response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        return response

    @app.middleware("http")
    async def client_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        token = trial_devices.CLIENT_CONTEXT.set(
            (request.headers.get("x-portal-client"), request.headers.get("x-portal-install"))
        )
        try:
            return await call_next(request)
        finally:
            trial_devices.CLIENT_CONTEXT.reset(token)

    errors.install(app)
    app.include_router(system_router)
    app.include_router(curriculum_router)
    app.include_router(identity_router)
    app.include_router(content.router)
    app.include_router(content.public)
    app.include_router(access_router)
    app.include_router(assessment_router)
    app.include_router(written_router)
    app.include_router(written_review_router)
    app.include_router(support_router)
    app.include_router(notifications_router)
    app.include_router(help_router)
    app.include_router(audit_router)
    if settings.dev_auth_enabled:  # refused in staging/production by the startup validator
        app.include_router(dev_auth.router)
    return app


app = create_app()
