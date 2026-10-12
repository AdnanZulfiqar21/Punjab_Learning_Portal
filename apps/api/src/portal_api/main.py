"""Application factory. Run locally:  uv run uvicorn portal_api.main:app --reload"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from portal_api import errors, observability
from portal_api.config import get_settings
from portal_api.modules.access import trial_devices
from portal_api.modules.access.products import router as products_router
from portal_api.modules.access.router import router as access_router
from portal_api.modules.analytics.economics import router as economics_router
from portal_api.modules.analytics.events import router as analytics_router
from portal_api.modules.analytics.funnels import router as funnel_router
from portal_api.modules.analytics.learning import router as learning_router
from portal_api.modules.analytics.trial_decisions import router as trial_decisions_router
from portal_api.modules.assessment.router import router as assessment_router
from portal_api.modules.audit.router import router as audit_router
from portal_api.modules.content import router as content
from portal_api.modules.content.concepts import router as concepts_router
from portal_api.modules.content.discovery import router as discovery_router
from portal_api.modules.content.inclusion import router as inclusion_router
from portal_api.modules.content.lectures import router as lectures_router
from portal_api.modules.content.packs import router as packs_router
from portal_api.modules.content.search import public as search_router
from portal_api.modules.content.search import studio as search_terms_router
from portal_api.modules.content.sources import router as sources_router
from portal_api.modules.content.study import router as study_router
from portal_api.modules.content.uploads import router as uploads_router
from portal_api.modules.curriculum.admin import router as catalogue_admin_router
from portal_api.modules.curriculum.router import router as curriculum_router
from portal_api.modules.exports.router import router as exports_router
from portal_api.modules.help.router import router as help_router
from portal_api.modules.identity import dev_auth
from portal_api.modules.identity.router import router as identity_router
from portal_api.modules.identity.settings import router as settings_router
from portal_api.modules.notifications.router import router as notifications_router
from portal_api.modules.support.router import router as support_router
from portal_api.modules.system.business import router as business_router
from portal_api.modules.system.clients import router as clients_router
from portal_api.modules.system.integrations import router as integrations_router
from portal_api.modules.system.router import router as system_router
from portal_api.modules.written.calibration import router as calibration_router
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
            "X-Portal-Platform",
            "X-Portal-App-Version",
            observability.HEADER,
        ],
        expose_headers=[observability.HEADER],
    )
    observability.install(app)

    @app.middleware("http")
    async def supported_client(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # P13.S1.T4 (CLIENTS-01): a native app below the enforced minimum version is told to update (426). Registered
        # before the security headers so the refusal carries them too.
        platform, version = request.headers.get("x-portal-platform"), request.headers.get("x-portal-app-version")
        if platform and version:
            from starlette.concurrency import run_in_threadpool

            from portal_api.db import get_sessionmaker
            from portal_api.modules.system import clients

            def check() -> dict[str, object] | None:
                with get_sessionmaker()() as db:
                    return clients.refuses(db, request.url.path, platform, version)

            refused = await run_in_threadpool(check)
            if refused is not None:
                return errors._problem(
                    request,
                    426,
                    "UPDATE_REQUIRED",
                    "This version of the app is no longer supported. Update it from your app store to continue.",
                    {**refused, "code_reason": "UPDATE_REQUIRED"},
                )
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # P18.S2.T1 (HEADERS-01): JSON API responses are never framed, sniffed or used as documents. The
        # development-only /docs page needs its own scripts, so it keeps the browser defaults.
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # P19.S3.T3 (ISOLATION-01): nothing is stored by a shared cache unless its route says so. Public catalogue
        # routes set their own `public, max-age`; every other response (personal, staff, errors) defaults to private.
        response.headers.setdefault("Cache-Control", "private, no-store")
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
    app.include_router(clients_router)
    app.include_router(curriculum_router)
    app.include_router(search_router)
    app.include_router(search_terms_router)
    app.include_router(identity_router)
    app.include_router(settings_router)
    app.include_router(content.router)
    app.include_router(content.public)
    app.include_router(lectures_router)
    app.include_router(discovery_router)
    app.include_router(study_router)
    app.include_router(concepts_router)
    app.include_router(inclusion_router)
    app.include_router(packs_router)
    app.include_router(sources_router)
    app.include_router(uploads_router)
    app.include_router(access_router)
    app.include_router(products_router)
    app.include_router(assessment_router)
    app.include_router(written_router)
    app.include_router(written_review_router)
    app.include_router(calibration_router)
    app.include_router(support_router)
    app.include_router(notifications_router)
    app.include_router(help_router)
    app.include_router(audit_router)
    app.include_router(exports_router)
    app.include_router(catalogue_admin_router)
    app.include_router(business_router)
    app.include_router(analytics_router)
    app.include_router(funnel_router)
    app.include_router(learning_router)
    app.include_router(economics_router)
    app.include_router(trial_decisions_router)
    app.include_router(integrations_router)
    if settings.dev_auth_enabled:  # refused in staging/production by the startup validator
        app.include_router(dev_auth.router)
    return app


app = create_app()
