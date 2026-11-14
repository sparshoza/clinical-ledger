"""FastAPI application factory. `app` is the deployed ASGI entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
from fastapi import APIRouter, FastAPI

from clinical_ledger import __version__
from clinical_ledger.logging import install_request_logging
from clinical_ledger.problems import install_problem_handlers
from clinical_ledger.routes import auth, cron, demo, events, health, records, stats, verify
from clinical_ledger.settings import Settings, get_settings
from clinical_ledger.storage.blobs import make_blob_store
from clinical_ledger.tenancy.seed import install_seed, load_seed

API_PREFIX = "/api/v1"
logger = logging.getLogger("clinical_ledger")

DESCRIPTION = (
    "A tamper-evident, versioned clinical record ledger. Every change is a new version, "
    "every event is chained by SHA-256, and each demo visitor gets a private tenant "
    "isolated by PostgreSQL row-level security. All data is synthetic (Synthea)."
)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Local runs with in-memory storage load the shared seed rows and files at startup."""
    settings: Settings = app.state.settings
    if settings.s3_backend == "memory":
        try:
            with psycopg.connect(settings.database_url, autocommit=True, connect_timeout=5) as conn:
                install_seed(conn, make_blob_store(settings), load_seed())
        except psycopg.Error:
            logger.warning("database unavailable at startup; seed not installed")
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        lifespan=_lifespan,
        title="Clinical Ledger API",
        version=__version__,
        description=DESCRIPTION,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings or get_settings()
    install_problem_handlers(app)
    install_request_logging(app)

    api = APIRouter(prefix=API_PREFIX)
    for module in (health, auth, records, events, verify, stats, demo, cron):
        api.include_router(module.router)
    app.include_router(api)
    return app


class _LazyApp:
    """Build the app on first request so importing this module needs no environment."""

    def __init__(self) -> None:
        self._app: FastAPI | None = None

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if self._app is None:
            self._app = create_app()
        await self._app(scope, receive, send)


app = _LazyApp()
