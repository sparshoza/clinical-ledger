"""Read path: latest, exact version, point-in-time, history and diffs.

Every read of record content is re-hashed against its content address and logged
as an event on the tenant's chain (an access audit trail).
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import jsonpatch
import psycopg

from clinical_ledger.errors import ContentTampered, RecordNotFound, VersionNotFound
from clinical_ledger.ledger.hashing import sha256_hex
from clinical_ledger.ledger.models import Actor, RecordContent, RecordSummary, VersionRef
from clinical_ledger.ledger.writer import LedgerWriter
from clinical_ledger.storage.blobs import BlobStore

_VERSION_COLUMNS = "v.record_id, v.version_no, v.content_hash, v.created_at, b.media_type"


def is_json_media(media_type: str) -> bool:
    return media_type == "application/json" or media_type.endswith("+json")


class LedgerReader:
    def __init__(
        self,
        conn: psycopg.Connection,
        store: BlobStore,
        tenant_id: UUID,
        actor: Actor,
        writer: LedgerWriter,
    ) -> None:
        self._conn = conn
        self._store = store
        self._tenant_id = tenant_id
        self._actor = actor
        self._writer = writer

    def latest(self, record_id: UUID) -> RecordContent:
        row = self._conn.execute(
            f"SELECT {_VERSION_COLUMNS} FROM record_heads h "  # noqa: S608
            "JOIN versions v ON v.tenant_id = h.tenant_id AND v.record_id = h.record_id "
            "AND v.version_no = h.latest_version_no "
            "JOIN blobs b ON b.content_hash = v.content_hash "
            "WHERE h.tenant_id = %s AND h.record_id = %s",
            (self._tenant_id, record_id),
        ).fetchone()
        if row is None:
            raise RecordNotFound(str(record_id))
        result = self._load(row)
        self._writer.append_event("record.read", record_id, result.ref.version_no, {})
        return result

    def version(self, record_id: UUID, version_no: int) -> RecordContent:
        result = self._load(self._version_row(record_id, version_no))
        self._writer.append_event("version.read", record_id, version_no, {})
        return result

    def as_of(self, record_id: UUID, at: datetime) -> RecordContent:
        self._require_record(record_id)
        row = self._conn.execute(
            f"SELECT {_VERSION_COLUMNS} FROM versions v "  # noqa: S608
            "JOIN blobs b ON b.content_hash = v.content_hash "
            "WHERE v.tenant_id = %s AND v.record_id = %s AND v.created_at <= %s "
            "ORDER BY v.created_at DESC, v.version_no DESC LIMIT 1",
            (self._tenant_id, record_id, at),
        ).fetchone()
        if row is None:
            raise VersionNotFound(f"{record_id} has no version at or before {at.isoformat()}")
        result = self._load(row)
        self._writer.append_event("version.read", record_id, result.ref.version_no, {})
        return result

    def list_versions(self, record_id: UUID) -> list[VersionRef]:
        self._require_record(record_id)
        rows = self._conn.execute(
            "SELECT record_id, version_no, content_hash, created_at FROM versions "
            "WHERE tenant_id = %s AND record_id = %s ORDER BY version_no",
            (self._tenant_id, record_id),
        ).fetchall()
        return [VersionRef(r[0], int(r[1]), str(r[2]), r[3]) for r in rows]

    def list_records(self, limit: int, cursor: UUID | None) -> list[RecordSummary]:
        rows = self._conn.execute(
            "SELECT r.id, r.kind, r.subject_ref, h.latest_version_no, h.updated_at "
            "FROM records r JOIN record_heads h ON h.tenant_id = r.tenant_id "
            "AND h.record_id = r.id WHERE r.tenant_id = %s AND (%s::uuid IS NULL OR r.id > %s) "
            "ORDER BY r.id LIMIT %s",
            (self._tenant_id, cursor, cursor, limit),
        ).fetchall()
        return [RecordSummary(r[0], str(r[1]), str(r[2]), int(r[3]), r[4]) for r in rows]

    def diff(self, record_id: UUID, from_no: int, to_no: int) -> list[dict[str, Any]]:
        before = self._load(self._version_row(record_id, from_no))
        after = self._load(self._version_row(record_id, to_no))
        self._writer.append_event(
            "version.read", record_id, to_no, {"purpose": "diff", "from": from_no, "to": to_no}
        )
        if is_json_media(before.media_type) and is_json_media(after.media_type):
            ops = jsonpatch.make_patch(json.loads(before.content), json.loads(after.content))
            return list(ops.patch)
        return [
            {
                "op": "binary",
                "from_hash": before.ref.content_hash,
                "to_hash": after.ref.content_hash,
                "from_size": len(before.content),
                "to_size": len(after.content),
            }
        ]

    def _require_record(self, record_id: UUID) -> None:
        exists = self._conn.execute(
            "SELECT 1 FROM record_heads WHERE tenant_id = %s AND record_id = %s",
            (self._tenant_id, record_id),
        ).fetchone()
        if exists is None:
            raise RecordNotFound(str(record_id))

    def _version_row(self, record_id: UUID, version_no: int) -> tuple[Any, ...]:
        self._require_record(record_id)
        row = self._conn.execute(
            f"SELECT {_VERSION_COLUMNS} FROM versions v "  # noqa: S608
            "JOIN blobs b ON b.content_hash = v.content_hash "
            "WHERE v.tenant_id = %s AND v.record_id = %s AND v.version_no = %s",
            (self._tenant_id, record_id, version_no),
        ).fetchone()
        if row is None:
            raise VersionNotFound(f"{record_id} has no version {version_no}")
        return tuple(row)

    def _load(self, row: tuple[Any, ...]) -> RecordContent:
        record_id, version_no, content_hash, created_at, media_type = row
        content = self.fetch_verified(str(content_hash))
        ref = VersionRef(record_id, int(version_no), str(content_hash), created_at)
        return RecordContent(ref=ref, content=content, media_type=str(media_type))

    def fetch_verified(self, content_hash: str) -> bytes:
        """Fetch a blob's bytes (honoring this tenant's overrides) and check its hash."""
        row = self._conn.execute(
            "SELECT storage_key FROM ("
            "SELECT 0 AS priority, o.storage_key FROM blob_overrides o "
            "WHERE o.tenant_id = %s AND o.content_hash = %s "
            "UNION ALL SELECT 1, storage_key FROM blobs WHERE content_hash = %s"
            ") candidates ORDER BY priority LIMIT 1",
            (self._tenant_id, content_hash, content_hash),
        ).fetchone()
        if row is None:
            raise ContentTampered(content_hash)
        content = self._store.get(str(row[0]))
        if sha256_hex(content) != content_hash:
            raise ContentTampered(content_hash)
        return content
