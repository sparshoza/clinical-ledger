"""Demo-only actions: tamper with the caller's own tenant, or start over."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from clinical_ledger.auth.permissions import Permission
from clinical_ledger.db import tenant_transaction
from clinical_ledger.deps import RequestContext, SeedDep, require
from clinical_ledger.problems import Problem
from clinical_ledger.routes.auth import SessionOut, start_session
from clinical_ledger.storage.blobs import override_key

router = APIRouter(prefix="/demo", tags=["demo"])

CanTamper = Annotated[RequestContext, Depends(require(Permission.TAMPER))]
CanReset = Annotated[RequestContext, Depends(require(Permission.RESET))]


class TamperIn(BaseModel):
    mode: Literal["event", "blob"]


class TamperOut(BaseModel):
    mode: Literal["event", "blob"]
    target_seq: int | None = None
    target_record_id: UUID | None = None
    target_version_no: int | None = None


def _flip_last_byte(data: bytes) -> bytes:
    if not data:
        return b"\x00"
    return data[:-1] + bytes([data[-1] ^ 0x01])


@router.post("/tamper", response_model=TamperOut, summary="Tamper with your own demo ledger")
def tamper(body: TamperIn, context: CanTamper) -> TamperOut:
    """Simulate an attacker. Only the caller's private demo tenant is changed."""
    conn, tenant = context.conn, context.tenant_id
    with tenant_transaction(conn, tenant):
        if body.mode == "event":
            head = conn.execute("SELECT max(seq) FROM events").fetchone()
            target = max(1, int(head[0] or 0) // 2) if head else 1
            conn.execute("SELECT demo_tamper_event(%s, %s)", (tenant, target))
            return TamperOut(mode="event", target_seq=target)

        row = conn.execute(
            "SELECT h.record_id, h.latest_version_no, h.latest_content_hash, b.storage_key, "
            "b.media_type FROM record_heads h JOIN blobs b ON b.content_hash = "
            "h.latest_content_hash ORDER BY h.record_id LIMIT 1"
        ).fetchone()
        if row is None:
            raise Problem(409, "nothing-to-tamper", "This ledger has no records")
        record_id, version_no, content_hash, storage_key, media_type = row
        key = override_key(tenant, content_hash)
        original = context.store.get(storage_key)
        context.store.put(key, _flip_last_byte(original), media_type)
        conn.execute(
            "INSERT INTO blob_overrides (tenant_id, content_hash, storage_key) "
            "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (tenant, content_hash, key),
        )
    return TamperOut(mode="blob", target_record_id=record_id, target_version_no=version_no)


@router.post("/reset", response_model=SessionOut, summary="Start over with a fresh demo ledger")
def reset(context: CanReset, seed: SeedDep) -> SessionOut:
    return start_session(context.conn, context.settings, seed, context.claims.role)
