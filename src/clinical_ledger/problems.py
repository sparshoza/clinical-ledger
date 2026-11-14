"""RFC 9457 problem details for every error response."""

import logging
from typing import Any

import psycopg
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from clinical_ledger.errors import (
    ContentTampered,
    ContentTooLarge,
    LedgerError,
    RecordNotFound,
    VersionNotFound,
)

PROBLEM_BASE = "https://clinical-ledger-weld.vercel.app/problems"
MEDIA_TYPE = "application/problem+json"
logger = logging.getLogger("clinical_ledger")


class Problem(Exception):
    """An error that becomes a problem+json response."""

    def __init__(self, status: int, slug: str, title: str, detail: str = "", **extra: Any) -> None:
        super().__init__(detail or title)
        self.status = status
        self.slug = slug
        self.title = title
        self.detail = detail
        self.extra = extra


def problem_response(
    status: int, slug: str, title: str, detail: str = "", **extra: Any
) -> JSONResponse:
    body = {"type": f"{PROBLEM_BASE}/{slug}", "title": title, "status": status, "detail": detail}
    body.update(extra)
    return JSONResponse(body, status_code=status, media_type=MEDIA_TYPE)


async def _problem_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, Problem):
        raise exc
    return problem_response(exc.status, exc.slug, exc.title, exc.detail, **exc.extra)


async def _http_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    slug = {404: "not-found", 405: "method-not-allowed"}.get(exc.status_code, "http-error")
    return problem_response(exc.status_code, slug, str(exc.detail), "")


async def _validation_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    errors = [
        {"loc": [str(part) for part in error.get("loc", ())], "msg": error.get("msg", "")}
        for error in exc.errors()
    ]
    return problem_response(
        422, "validation-error", "The request is not valid", "See errors.", errors=errors
    )


_LEDGER_ERRORS: dict[type[Exception], tuple[int, str, str]] = {
    RecordNotFound: (404, "not-found", "Record not found"),
    VersionNotFound: (404, "not-found", "Version not found"),
    ContentTooLarge: (413, "content-too-large", "The content is too large"),
    ContentTampered: (409, "content-tampered", "Stored content does not match its hash"),
}


async def _ledger_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, LedgerError):
        raise exc
    status, slug, title = _LEDGER_ERRORS.get(type(exc), (400, "ledger-error", "Request failed"))
    return problem_response(status, slug, title, str(exc))


async def _unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    return problem_response(
        503,
        "unavailable",
        "The service is temporarily unavailable",
        "The database or storage could not be reached. Try again in a few seconds.",
    )


# Storage answers that mean "try again later", not "you asked for something wrong".
_STORAGE_OUTAGE_CODES = {"ServiceUnavailable", "SlowDown", "InternalError", "RequestTimeout"}


async def _storage_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ClientError):
        return _internal_problem()
    error = exc.response.get("Error", {})
    status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 500))
    if status >= 500 or error.get("Code") in _STORAGE_OUTAGE_CODES:
        return await _unavailable_handler(request, exc)
    logger.exception("storage request failed")
    return _internal_problem()


async def _unexpected_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error")
    return _internal_problem()


def _internal_problem() -> JSONResponse:
    return problem_response(
        500,
        "internal-error",
        "Something went wrong on our side",
        "The error has been logged. Try again, or reset the demo if it keeps happening.",
    )


def install_problem_handlers(app: FastAPI) -> None:
    app.add_exception_handler(Problem, _problem_handler)
    app.add_exception_handler(LedgerError, _ledger_handler)
    app.add_exception_handler(psycopg.OperationalError, _unavailable_handler)
    app.add_exception_handler(BotoCoreError, _unavailable_handler)
    app.add_exception_handler(ClientError, _storage_error_handler)
    app.add_exception_handler(Exception, _unexpected_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
