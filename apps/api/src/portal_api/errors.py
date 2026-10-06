"""Common error shape (RFC 9457 problem details) used by every module (P01.S3.T1)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError


class AppError(Exception):
    status = 500
    code = "INTERNAL"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFound(AppError):
    status = 404
    code = "NOT_FOUND"


def _problem(request: Request, status: int, code: str, detail: str, **extra: object) -> JSONResponse:
    body = {
        "type": f"https://errors.portal.invalid/{code.lower()}",
        "title": code,
        "status": status,
        "detail": detail,
        "correlation_id": getattr(request.state, "correlation_id", None),
        **extra,
    }
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return _problem(request, exc.status, exc.code, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errs = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return _problem(request, 422, "VALIDATION_FAILED", "The request is invalid.", errors=errs)

    @app.exception_handler(OperationalError)
    async def _db_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
        return _problem(request, 503, "SERVICE_UNAVAILABLE", "The service is temporarily unavailable. Please retry.")
