"""RFC 9457 problem details for every error response."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_BASE = "https://clinical-ledger.vercel.app/problems"
MEDIA_TYPE = "application/problem+json"


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


def install_problem_handlers(app: FastAPI) -> None:
    app.add_exception_handler(Problem, _problem_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
