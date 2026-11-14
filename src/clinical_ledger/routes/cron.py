"""Scheduled maintenance, called by the host's cron with a shared secret."""

import hmac
from typing import Annotated

from fastapi import APIRouter, Header
from pydantic import BaseModel

from clinical_ledger.deps import ConnDep, SettingsDep, StoreDep, bearer_token
from clinical_ledger.problems import Problem

router = APIRouter(prefix="/cron", tags=["maintenance"])


class CleanupOut(BaseModel):
    removed: int


@router.get("/cleanup", response_model=CleanupOut, summary="Delete expired demo tenants")
def cleanup(
    conn: ConnDep,
    settings: SettingsDep,
    store: StoreDep,
    authorization: Annotated[str | None, Header()] = None,
) -> CleanupOut:
    token = bearer_token(authorization) or ""
    if not hmac.compare_digest(token.encode(), settings.cron_secret.encode()):
        raise Problem(401, "unauthorized", "Missing or wrong cron secret")
    # The tenants table has no row-level security, so the expired ids are readable here; the
    # rows themselves are deleted by the owner-defined function.
    expired = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM tenants WHERE kind = 'demo' AND expires_at < now()"
        ).fetchall()
    ]
    row = conn.execute("SELECT cleanup_expired_tenants()").fetchone()
    for tenant_id in expired:
        # Tampered copies exist only for demo tenants and go with them. Shared content blobs
        # stay: other tenants may reference them.
        store.delete_prefix(f"overrides/{tenant_id}/")
    return CleanupOut(removed=int(row[0]) if row else 0)
