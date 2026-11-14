"""Append-only write path: blobs, versions, heads and the per-tenant hash chain.

Callers own the transaction (see `db.tenant_transaction`); every method here runs
inside it so a version, its head update and its event commit together or not at all.
"""

import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from clinical_ledger.errors import ContentTooLarge, RecordNotFound
from clinical_ledger.ledger.hashing import (
    GENESIS_HASH,
    compute_event_hash,
    event_hash_fields,
    sha256_hex,
)
from clinical_ledger.ledger.models import Actor, EventRow, VersionRef
from clinical_ledger.settings import Settings
from clinical_ledger.storage.blobs import BlobStore, blob_key


def chain_lock_key(tenant_id: UUID) -> int:
    """Advisory lock key for a tenant's chain: first 8 bytes as a signed int64."""
    return int.from_bytes(tenant_id.bytes[:8], "big", signed=True)


class LedgerWriter:
    def __init__(
        self,
        conn: psycopg.Connection,
        store: BlobStore,
        tenant_id: UUID,
        actor: Actor,
        settings: Settings,
    ) -> None:
        self._conn = conn
        self._store = store
        self._tenant_id = tenant_id
        self._actor = actor
        self._settings = settings

    def create_record(
        self, kind: str, subject_ref: str, content: bytes, media_type: str, note: str = ""
    ) -> VersionRef:
        content_hash = self._store_blob(content, media_type)
        record_id = uuid.uuid4()
        now = datetime.now(UTC)
        self._conn.execute(
            "INSERT INTO records (tenant_id, id, kind, subject_ref, created_at, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (self._tenant_id, record_id, kind, subject_ref, now, self._actor.id),
        )
        ref = self._insert_version(record_id, 1, content_hash, note, now)
        self._conn.execute(
            "INSERT INTO record_heads (tenant_id, record_id, latest_version_no, "
            "latest_content_hash, updated_at) VALUES (%s, %s, 1, %s, %s)",
            (self._tenant_id, record_id, content_hash, now),
        )
        self.append_event(
            "record.created", record_id, 1, {"kind": kind, "content_hash": content_hash}
        )
        return ref

    def add_version(
        self, record_id: UUID, content: bytes, media_type: str, note: str = ""
    ) -> VersionRef:
        row = self._conn.execute(
            "SELECT latest_version_no FROM record_heads "
            "WHERE tenant_id = %s AND record_id = %s FOR UPDATE",
            (self._tenant_id, record_id),
        ).fetchone()
        if row is None:
            raise RecordNotFound(str(record_id))
        content_hash = self._store_blob(content, media_type)
        version_no = int(row[0]) + 1
        now = datetime.now(UTC)
        ref = self._insert_version(record_id, version_no, content_hash, note, now)
        self._conn.execute(
            "UPDATE record_heads SET latest_version_no = %s, latest_content_hash = %s, "
            "updated_at = %s WHERE tenant_id = %s AND record_id = %s",
            (version_no, content_hash, now, self._tenant_id, record_id),
        )
        self.append_event("version.added", record_id, version_no, {"content_hash": content_hash})
        return ref

    def append_event(
        self,
        event_type: str,
        record_id: UUID | None,
        version_no: int | None,
        payload: dict[str, Any],
    ) -> EventRow:
        self._conn.execute("SELECT pg_advisory_xact_lock(%s)", (chain_lock_key(self._tenant_id),))
        last = self._conn.execute(
            "SELECT seq, event_hash FROM events WHERE tenant_id = %s ORDER BY seq DESC LIMIT 1",
            (self._tenant_id,),
        ).fetchone()
        seq, prev_hash = (int(last[0]) + 1, str(last[1])) if last else (1, GENESIS_HASH)
        occurred_at = datetime.now(UTC)
        fields = event_hash_fields(
            tenant_id=self._tenant_id,
            seq=seq,
            event_type=event_type,
            record_id=record_id,
            version_no=version_no,
            actor=self._actor.id,
            actor_role=self._actor.role,
            occurred_at=occurred_at,
            payload=payload,
        )
        event_hash = compute_event_hash(prev_hash, fields)
        self._conn.execute(
            "INSERT INTO events (tenant_id, seq, event_type, record_id, version_no, actor, "
            "actor_role, occurred_at, payload, prev_hash, event_hash) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                self._tenant_id,
                seq,
                event_type,
                record_id,
                version_no,
                self._actor.id,
                self._actor.role,
                occurred_at,
                Jsonb(payload),
                prev_hash,
                event_hash,
            ),
        )
        if seq % self._settings.checkpoint_interval == 0:
            self._conn.execute(
                "INSERT INTO checkpoints (tenant_id, seq, event_hash) VALUES (%s, %s, %s)",
                (self._tenant_id, seq, event_hash),
            )
        return EventRow(
            seq=seq,
            event_type=event_type,
            record_id=record_id,
            version_no=version_no,
            actor=self._actor.id,
            actor_role=self._actor.role,
            occurred_at=occurred_at,
            payload=payload,
            prev_hash=prev_hash,
            event_hash=event_hash,
        )

    def _store_blob(self, content: bytes, media_type: str) -> str:
        limit = self._settings.max_content_bytes
        if len(content) > limit:
            raise ContentTooLarge(len(content), limit)
        content_hash = sha256_hex(content)
        exists = self._conn.execute(
            "SELECT 1 FROM blobs WHERE content_hash = %s", (content_hash,)
        ).fetchone()
        if exists is None:
            key = blob_key(content_hash)
            self._store.put(key, content, media_type)
            self._conn.execute(
                "INSERT INTO blobs (content_hash, size_bytes, media_type, storage_key) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (content_hash) DO NOTHING",
                (content_hash, len(content), media_type, key),
            )
        return content_hash

    def _insert_version(
        self, record_id: UUID, version_no: int, content_hash: str, note: str, now: datetime
    ) -> VersionRef:
        self._conn.execute(
            "INSERT INTO versions (tenant_id, record_id, version_no, content_hash, "
            "created_at, created_by, note) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (self._tenant_id, record_id, version_no, content_hash, now, self._actor.id, note),
        )
        return VersionRef(
            record_id=record_id, version_no=version_no, content_hash=content_hash, created_at=now
        )
