"""Canonical JSON and SHA-256 hashing for the event chain.

Every hash in the system goes through this module so that a value hashed at write
time produces the same bytes when it is re-read from PostgreSQL and verified.
Floats are rejected because their text form can change on a database round trip.
"""

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

GENESIS_HASH = "0" * 64


def format_ts(dt: datetime) -> str:
    """Format an aware datetime as UTC with microseconds, e.g. 2026-01-02T04:30:00.000005Z."""
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _reject_floats(value: object) -> None:
    if isinstance(value, float | Decimal):
        raise TypeError(f"floats are not allowed in hashed data: {value!r}")
    if isinstance(value, Mapping):
        for item in value.values():
            _reject_floats(item)
    elif isinstance(value, list | tuple):
        for item in value:
            _reject_floats(item)


def _default(value: object) -> str:
    if isinstance(value, datetime):
        return format_ts(value)
    raise TypeError(f"value of type {type(value).__name__} is not JSON serializable")


def canonical_json(value: object) -> bytes:
    """Serialize with sorted keys, no whitespace, UTF-8, and RFC 3339 UTC timestamps."""
    _reject_floats(value)
    text = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_default
    )
    return text.encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def event_hash_fields(
    *,
    tenant_id: UUID,
    seq: int,
    event_type: str,
    record_id: UUID | None,
    version_no: int | None,
    actor: UUID,
    actor_role: str,
    occurred_at: datetime,
    payload: Mapping[str, object],
) -> dict[str, object]:
    """The exact fields an event's hash covers. Used by both the writer and the verifier."""
    return {
        "tenant_id": str(tenant_id),
        "seq": seq,
        "event_type": event_type,
        "record_id": str(record_id) if record_id is not None else None,
        "version_no": version_no,
        "actor": str(actor),
        "actor_role": actor_role,
        "occurred_at": format_ts(occurred_at),
        "payload": dict(payload),
    }


def compute_event_hash(prev_hash: str, fields: Mapping[str, object]) -> str:
    """event_hash = sha256(prev_hash || canonical_json(fields))."""
    return sha256_hex(prev_hash.encode("ascii") + canonical_json(dict(fields)))
