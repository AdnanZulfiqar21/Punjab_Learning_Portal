"""Common error shape (RFC 9457 problem details) used by every module (P01.S3.T1)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError


class AppError(Exception):
    status = 500
    code = "INTERNAL"

    def __init__(self, detail: str, **extra: object) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extra = extra  # additional problem members, e.g. validation errors or the current state on a conflict


class NotFound(AppError):
    status = 404
    code = "NOT_FOUND"


class Gone(AppError):
    status = 410
    code = "GONE"


class Unauthorized(AppError):
    status = 401
    code = "UNAUTHENTICATED"


class Forbidden(AppError):
    status = 403
    code = "FORBIDDEN"


class Conflict(AppError):
    status = 409
    code = "CONFLICT"


class AttemptFinalised(Conflict):
    """A genuinely new answer write for an attempt that has already been finalised (§10.5)."""

    code = "ATTEMPT_FINALISED"


class TooLarge(AppError):
    status = 413
    code = "PAYLOAD_TOO_LARGE"


class Unprocessable(AppError):
    """The request is well-formed but breaks a domain rule (e.g. content fails publication validation)."""

    status = 422
    code = "RULE_FAILED"


def _problem(
    request: Request, status: int, code: str, detail: str, extra: dict[str, object] | None = None
) -> JSONResponse:
    extra = extra or {}
    body = {
        "type": f"https://errors.portal.invalid/{code.lower()}",
        "title": code,
        "status": status,
        "detail": detail,
        "correlation_id": getattr(request.state, "correlation_id", None),
    }
    body.update({k: v for k, v in extra.items() if k not in body})  # extras never override the standard members
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        response = _problem(request, exc.status, exc.code, exc.detail, exc.extra)
        if exc.status == 401:
            response.headers["WWW-Authenticate"] = 'Bearer realm="portal"'
        return response

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errs = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return _problem(request, 422, "VALIDATION_FAILED", "The request is invalid.", {"errors": errs})

    @app.exception_handler(OperationalError)
    async def _db_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
        # Log the driver error class and first line (no parameters, which may hold user data) with the correlation id.
        orig = getattr(exc, "orig", exc)
        first_line = str(orig).splitlines()[0][:200] if str(orig) else ""
        logging.getLogger("portal_api.db").warning(
            "database unavailable: %s: %s path=%s cid=%s",
            type(orig).__name__,
            first_line,
            request.url.path,
            getattr(request.state, "correlation_id", None),
        )
        return _problem(request, 503, "SERVICE_UNAVAILABLE", "The service is temporarily unavailable. Please retry.")
