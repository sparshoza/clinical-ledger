"""Records: create, add versions, read (latest, exact, as of), history and diffs."""

import json
from datetime import datetime
from typing import Annotated
from uuid import UUID

import jsonpatch
from fastapi import APIRouter, Depends, Query, status

from clinical_ledger.auth.permissions import Permission
from clinical_ledger.db import tenant_transaction
from clinical_ledger.deps import RequestContext, SeedDep, require
from clinical_ledger.errors import RecordNotFound
from clinical_ledger.ledger.content import encode_document, is_json_media
from clinical_ledger.ledger.reader import LedgerReader
from clinical_ledger.ledger.writer import LedgerWriter
from clinical_ledger.problems import Problem
from clinical_ledger.routes.schemas import (
    DiffOut,
    RecordContentOut,
    RecordCreate,
    RecordPage,
    RecordSummaryOut,
    VersionCreate,
    VersionList,
    VersionOut,
)
from clinical_ledger.tenancy.seed import next_edit

router = APIRouter(prefix="/records", tags=["records"])

CanRead = Annotated[RequestContext, Depends(require(Permission.READ_CONTENT))]
CanWrite = Annotated[RequestContext, Depends(require(Permission.WRITE_RECORDS))]
CanList = Annotated[RequestContext, Depends(require(Permission.READ_EVENTS))]
MAX_PAGE = 100


def ledger(context: RequestContext) -> tuple[LedgerWriter, LedgerReader]:
    writer = LedgerWriter(
        context.conn, context.store, context.tenant_id, context.actor, context.settings
    )
    reader = LedgerReader(context.conn, context.store, context.tenant_id, context.actor, writer)
    return writer, reader


def _content(body: RecordCreate | VersionCreate) -> tuple[bytes, str]:
    try:
        return body.to_bytes()
    except ValueError as exc:
        raise Problem(422, "validation-error", "The content is not valid", str(exc)) from exc


@router.get("", response_model=RecordPage, summary="List records")
def list_records(
    context: CanList,
    limit: Annotated[int, Query(ge=1)] = 50,
    cursor: UUID | None = None,
) -> RecordPage:
    size = min(limit, MAX_PAGE)
    _, reader = ledger(context)
    with tenant_transaction(context.conn, context.tenant_id):
        items = reader.list_records(size, cursor)
    return RecordPage(
        items=[RecordSummaryOut(**item.__dict__) for item in items],
        next_cursor=items[-1].id if len(items) == size else None,
    )


@router.post(
    "", response_model=VersionOut, status_code=status.HTTP_201_CREATED, summary="Create a record"
)
def create_record(body: RecordCreate, context: CanWrite) -> VersionOut:
    data, media_type = _content(body)
    writer, _ = ledger(context)
    with tenant_transaction(context.conn, context.tenant_id):
        ref = writer.create_record(body.kind, body.subject_ref, data, media_type, body.note)
    return VersionOut.of(ref, body.note)


@router.get("/{record_id}", response_model=RecordContentOut, summary="Read a record")
def read_record(
    record_id: UUID, context: CanRead, as_of: datetime | None = None
) -> RecordContentOut:
    """The latest version, or the version that was current at `as_of`."""
    _, reader = ledger(context)
    with tenant_transaction(context.conn, context.tenant_id):
        content = reader.as_of(record_id, as_of) if as_of else reader.latest(record_id)
    return RecordContentOut.of(content)


@router.post(
    "/{record_id}/versions",
    response_model=VersionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a version",
)
def add_version(record_id: UUID, body: VersionCreate, context: CanWrite) -> VersionOut:
    data, media_type = _content(body)
    writer, _ = ledger(context)
    with tenant_transaction(context.conn, context.tenant_id):
        ref = writer.add_version(record_id, data, media_type, body.note)
    return VersionOut.of(ref, body.note)


@router.get("/{record_id}/versions", response_model=VersionList, summary="List versions")
def list_versions(record_id: UUID, context: CanList) -> VersionList:
    _, reader = ledger(context)
    with tenant_transaction(context.conn, context.tenant_id):
        refs = reader.list_versions(record_id)
        notes: dict[int, str] = dict(
            context.conn.execute(
                "SELECT version_no, note FROM versions WHERE tenant_id = %s AND record_id = %s",
                (context.tenant_id, record_id),
            ).fetchall()
        )
    return VersionList(items=[VersionOut.of(ref, notes.get(ref.version_no)) for ref in refs])


@router.get(
    "/{record_id}/versions/{version_no}",
    response_model=RecordContentOut,
    summary="Read one version",
)
def read_version(record_id: UUID, version_no: int, context: CanRead) -> RecordContentOut:
    _, reader = ledger(context)
    with tenant_transaction(context.conn, context.tenant_id):
        content = reader.version(record_id, version_no)
    return RecordContentOut.of(content)


@router.get("/{record_id}/diff", response_model=DiffOut, summary="Compare two versions")
def diff_versions(
    record_id: UUID,
    context: CanRead,
    from_version: Annotated[int, Query(alias="from", ge=1)],
    to_version: Annotated[int, Query(alias="to", ge=1)],
) -> DiffOut:
    _, reader = ledger(context)
    with tenant_transaction(context.conn, context.tenant_id):
        ops = reader.diff(record_id, from_version, to_version)
    return DiffOut(from_version=from_version, to_version=to_version, ops=ops)


@router.post(
    "/{record_id}/demo-edit",
    response_model=VersionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Apply the next realistic demo edit",
)
def demo_edit(record_id: UUID, context: CanWrite, seed: SeedDep) -> VersionOut:
    """Add a version made from the record's latest JSON plus the next pre-written edit."""
    writer, reader = ledger(context)
    with tenant_transaction(context.conn, context.tenant_id):
        kind_row = context.conn.execute(
            "SELECT kind FROM records WHERE tenant_id = %s AND id = %s",
            (context.tenant_id, record_id),
        ).fetchone()
        if kind_row is None:
            raise RecordNotFound(str(record_id))
        current = reader.latest(record_id)
        if not is_json_media(current.media_type):
            raise Problem(409, "not-json", "Demo edits apply to JSON records only")
        edit = next_edit(seed, str(kind_row[0]), current.ref.version_no)
        document = jsonpatch.apply_patch(json.loads(current.content), list(edit.json_patch))
        ref = writer.add_version(
            record_id, encode_document(document), current.media_type, edit.description
        )
    return VersionOut.of(ref, edit.description)
