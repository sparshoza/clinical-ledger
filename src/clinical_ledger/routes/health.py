"""Liveness of the database and object storage."""

import psycopg
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from clinical_ledger.deps import SettingsDep
from clinical_ledger.storage.blobs import make_blob_store

router = APIRouter(tags=["health"])


@router.get("/health", summary="Check the database and storage")
def health(settings: SettingsDep) -> JSONResponse:
    database = storage = "ok"
    try:
        with psycopg.connect(settings.database_url, connect_timeout=5) as conn:
            conn.execute("SELECT 1")
    except psycopg.Error:
        database = "unavailable"
    try:
        make_blob_store(settings).exists("health/probe")
    except Exception:  # noqa: BLE001 - any storage failure means unavailable
        storage = "unavailable"
    ok = database == storage == "ok"
    body = {"status": "ok" if ok else "degraded", "database": database, "storage": storage}
    return JSONResponse(body, status_code=200 if ok else 503)
