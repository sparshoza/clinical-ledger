"""Counts and the chain head for the caller's tenant."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from clinical_ledger.auth.permissions import Permission
from clinical_ledger.db import tenant_transaction
from clinical_ledger.deps import RequestContext, require

router = APIRouter(tags=["stats"])

CanReadEvents = Annotated[RequestContext, Depends(require(Permission.READ_EVENTS))]


class LastVerify(BaseModel):
    at: datetime
    ok: bool


class StatsOut(BaseModel):
    events: int
    records: int
    versions: int
    head_seq: int
    head_hash: str
    last_checkpoint_seq: int | None
    last_verify: LastVerify | None
    tenant_expires_at: datetime | None


@router.get("/stats", response_model=StatsOut, summary="Counts and chain head")
def stats(context: CanReadEvents) -> StatsOut:
    with tenant_transaction(context.conn, context.tenant_id):
        row = context.conn.execute(
            "SELECT (SELECT count(*) FROM events), (SELECT count(*) FROM records), "
            "(SELECT count(*) FROM versions), "
            "(SELECT max(seq) FROM checkpoints), "
            "(SELECT expires_at FROM tenants WHERE id = %s)",
            (context.tenant_id,),
        ).fetchone()
        head = context.conn.execute(
            "SELECT seq, event_hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        verify = context.conn.execute(
            "SELECT occurred_at, payload->>'ok' FROM events WHERE event_type = 'verify.run' "
            "ORDER BY seq DESC LIMIT 1"
        ).fetchone()
    assert row is not None  # noqa: S101 - aggregate query always returns a row
    return StatsOut(
        events=row[0],
        records=row[1],
        versions=row[2],
        last_checkpoint_seq=row[3],
        tenant_expires_at=row[4],
        head_seq=head[0] if head else 0,
        head_hash=head[1] if head else "",
        last_verify=LastVerify(at=verify[0], ok=verify[1] == "true") if verify else None,
    )
