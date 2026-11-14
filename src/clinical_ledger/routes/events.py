"""The audit log: the tenant's hash-chained events, newest first."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from clinical_ledger.auth.permissions import Permission
from clinical_ledger.db import tenant_transaction
from clinical_ledger.deps import RequestContext, require
from clinical_ledger.ledger.models import EventRow
from clinical_ledger.routes.schemas import EventOut, EventPage

router = APIRouter(prefix="/events", tags=["events"])

CanReadEvents = Annotated[RequestContext, Depends(require(Permission.READ_EVENTS))]
MAX_PAGE = 100


@router.get("", response_model=EventPage, summary="List events, newest first")
def list_events(
    context: CanReadEvents,
    limit: Annotated[int, Query(ge=1)] = 50,
    before_seq: Annotated[int | None, Query(ge=1)] = None,
    record_id: UUID | None = None,
    event_type: str | None = None,
    actor: UUID | None = None,
) -> EventPage:
    size = min(limit, MAX_PAGE)
    clauses = ["tenant_id = %s"]
    params: list[Any] = [context.tenant_id]
    for column, value in (
        ("seq <", before_seq),
        ("record_id =", record_id),
        ("event_type =", event_type),
        ("actor =", actor),
    ):
        if value is not None:
            clauses.append(f"{column} %s")
            params.append(value)
    params.append(size)
    with tenant_transaction(context.conn, context.tenant_id):
        rows = context.conn.execute(
            "SELECT seq, event_type, record_id, version_no, actor, actor_role, occurred_at, "  # noqa: S608
            f"payload, prev_hash, event_hash FROM events WHERE {' AND '.join(clauses)} "
            "ORDER BY seq DESC LIMIT %s",
            params,
        ).fetchall()
    items = [EventOut.of(EventRow(*row)) for row in rows]
    return EventPage(
        items=items, next_before_seq=items[-1].seq if len(items) == size and items else None
    )
