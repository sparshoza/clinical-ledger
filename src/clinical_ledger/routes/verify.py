"""Run a verification of the caller's chain and stored content."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from clinical_ledger.auth.permissions import Permission
from clinical_ledger.db import tenant_transaction
from clinical_ledger.deps import RequestContext, require
from clinical_ledger.ledger.verify import Reason, verify_chain
from clinical_ledger.ledger.writer import LedgerWriter

router = APIRouter(tags=["verify"])

CanVerify = Annotated[RequestContext, Depends(require(Permission.RUN_VERIFY))]


class VerifyIn(BaseModel):
    from_checkpoint: bool = False


class VerifyOut(BaseModel):
    ok: bool
    checked_events: int
    checked_blobs: int
    first_broken_seq: int | None
    reason: Reason | None


@router.post("/verify", response_model=VerifyOut, summary="Verify the chain and stored content")
def verify(body: VerifyIn, context: CanVerify) -> VerifyOut:
    with tenant_transaction(context.conn, context.tenant_id):
        result = verify_chain(
            context.conn, context.store, context.tenant_id, from_checkpoint=body.from_checkpoint
        )
        LedgerWriter(
            context.conn, context.store, context.tenant_id, context.actor, context.settings
        ).append_event(
            "verify.run",
            None,
            None,
            {
                "ok": result.ok,
                "checked_events": result.checked_events,
                "first_broken_seq": result.first_broken_seq,
            },
        )
    return VerifyOut(**result.__dict__)
