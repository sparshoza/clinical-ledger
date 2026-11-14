"""Request and response bodies shared by the record and event routes."""

import base64
from datetime import datetime
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from clinical_ledger.ledger.content import JSON_MEDIA_TYPE, encode_document, is_json_media
from clinical_ledger.ledger.models import EventRow, RecordContent, VersionRef


class ContentIn(BaseModel):
    """Exactly one of `content_json` or `content_b64`."""

    content_json: Any | None = None
    content_b64: str | None = None
    media_type: str | None = None
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def one_content_field(self) -> Self:
        has_json = "content_json" in self.model_fields_set
        if has_json == (self.content_b64 is not None):
            raise ValueError("send exactly one of content_json or content_b64")
        return self

    def to_bytes(self) -> tuple[bytes, str]:
        if self.content_b64 is not None:
            try:
                data = base64.b64decode(self.content_b64, validate=True)
            except ValueError as exc:
                raise ValueError("content_b64 is not valid base64") from exc
            return data, self.media_type or "application/octet-stream"
        return encode_document(self.content_json), self.media_type or JSON_MEDIA_TYPE


class RecordCreate(ContentIn):
    kind: str = Field(min_length=1, max_length=64)
    subject_ref: str = Field(min_length=1, max_length=200)


class VersionCreate(ContentIn):
    pass


class VersionOut(BaseModel):
    record_id: UUID
    version_no: int
    content_hash: str
    created_at: datetime
    note: str | None = None

    @classmethod
    def of(cls, ref: VersionRef, note: str | None = None) -> "VersionOut":
        return cls(
            record_id=ref.record_id,
            version_no=ref.version_no,
            content_hash=ref.content_hash,
            created_at=ref.created_at,
            note=note,
        )


class RecordSummaryOut(BaseModel):
    id: UUID
    kind: str
    subject_ref: str
    latest_version_no: int
    updated_at: datetime


class RecordPage(BaseModel):
    items: list[RecordSummaryOut]
    next_cursor: UUID | None


class RecordContentOut(BaseModel):
    version: VersionOut
    media_type: str
    content_json: Any | None = None
    content_b64: str | None = None

    @classmethod
    def of(cls, content: RecordContent) -> "RecordContentOut":
        out = cls(version=VersionOut.of(content.ref), media_type=content.media_type)
        if is_json_media(content.media_type):
            import json

            out.content_json = json.loads(content.content)
        else:
            out.content_b64 = base64.b64encode(content.content).decode("ascii")
        return out


class VersionList(BaseModel):
    items: list[VersionOut]


class DiffOut(BaseModel):
    from_version: int
    to_version: int
    ops: list[dict[str, Any]]


class EventOut(BaseModel):
    seq: int
    event_type: str
    record_id: UUID | None
    version_no: int | None
    actor: UUID
    actor_role: str
    occurred_at: datetime
    payload: dict[str, Any]
    prev_hash: str
    event_hash: str

    @classmethod
    def of(cls, row: EventRow) -> "EventOut":
        return cls(**row.__dict__)


class EventPage(BaseModel):
    items: list[EventOut]
    next_before_seq: int | None
