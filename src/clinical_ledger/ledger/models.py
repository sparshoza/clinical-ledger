"""Value objects shared by the ledger's write, read and verify paths."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class Actor:
    id: UUID
    role: str


@dataclass(frozen=True)
class VersionRef:
    record_id: UUID
    version_no: int
    content_hash: str
    created_at: datetime


@dataclass(frozen=True)
class EventRow:
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
