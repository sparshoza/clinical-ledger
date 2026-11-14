"""Scheduled maintenance, called by the host's cron with a shared secret."""

import hmac
from typing import Annotated

from fastapi import APIRouter, Header
from pydantic import BaseModel

from clinical_ledger.deps import ConnDep, SettingsDep, bearer_token
from clinical_ledger.problems import Problem

router = APIRouter(prefix="/cron", tags=["maintenance"])


class CleanupOut(BaseModel):
    removed: int


@router.get("/cleanup", response_model=CleanupOut, summary="Delete expired demo tenants")
def cleanup(
    conn: ConnDep,
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> CleanupOut:
    token = bearer_token(authorization) or ""
    if not hmac.compare_digest(token.encode(), settings.cron_secret.encode()):
        raise Problem(401, "unauthorized", "Missing or wrong cron secret")
    row = conn.execute("SELECT cleanup_expired_tenants()").fetchone()
    conn.commit()
    return CleanupOut(removed=int(row[0]) if row else 0)
