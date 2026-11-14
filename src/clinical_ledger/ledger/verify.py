"""Verification: recompute the tenant's hash chain and re-hash every stored blob."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

import psycopg

from clinical_ledger.ledger.hashing import (
    GENESIS_HASH,
    compute_event_hash,
    event_hash_fields,
    sha256_hex,
)
from clinical_ledger.storage.blobs import BlobNotFound, BlobStore

Reason = Literal["hash_mismatch", "broken_link", "blob_mismatch"]
BATCH_SIZE = 5_000


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    checked_events: int
    checked_blobs: int
    first_broken_seq: int | None
    reason: Reason | None
    # For a chain break: the hash the ledger holds and the one recomputed from the fields
    # (for a broken link, the previous hash carried forward and the one it should be).
    stored_hash: str | None = None
    computed_hash: str | None = None


def verify_chain(
    conn: psycopg.Connection, store: BlobStore, tenant_id: UUID, *, from_checkpoint: bool = False
) -> VerifyResult:
    """Walk the chain from genesis (or the latest checkpoint), then check blob contents.

    Must run inside `tenant_transaction` (the event cursor is server-side).
    """
    start_seq, prev_hash = 0, GENESIS_HASH
    blob_since = None
    if from_checkpoint:
        checkpoint = conn.execute(
            "SELECT seq, event_hash, created_at FROM checkpoints WHERE tenant_id = %s "
            "ORDER BY seq DESC LIMIT 1",
            (tenant_id,),
        ).fetchone()
        if checkpoint is not None:
            start_seq, prev_hash, blob_since = int(checkpoint[0]), str(checkpoint[1]), checkpoint[2]
            anchored = conn.execute(
                "SELECT event_hash FROM events WHERE tenant_id = %s AND seq = %s",
                (tenant_id, start_seq),
            ).fetchone()
            if anchored is None or str(anchored[0]) != prev_hash:
                stored = None if anchored is None else str(anchored[0])
                return VerifyResult(False, 0, 0, start_seq, "hash_mismatch", stored, prev_hash)

    checked = 0
    with conn.cursor(name="verify_events") as cursor:
        cursor.itersize = BATCH_SIZE
        cursor.execute(
            "SELECT seq, event_type, record_id, version_no, actor, actor_role, occurred_at, "
            "payload, prev_hash, event_hash FROM events WHERE tenant_id = %s AND seq > %s "
            "ORDER BY seq",
            (tenant_id, start_seq),
        )
        for row in cursor:
            seq, event_type, record_id, version_no, actor, role, occurred_at, payload = row[:8]
            stored_prev, stored_hash = str(row[8]), str(row[9])
            checked += 1
            if stored_prev != prev_hash:
                return VerifyResult(
                    False, checked, 0, int(seq), "broken_link", stored_prev, prev_hash
                )
            fields = event_hash_fields(
                tenant_id=tenant_id,
                seq=int(seq),
                event_type=event_type,
                record_id=record_id,
                version_no=version_no,
                actor=actor,
                actor_role=role,
                occurred_at=occurred_at,
                payload=payload,
            )
            computed = compute_event_hash(prev_hash, fields)
            if computed != stored_hash:
                return VerifyResult(
                    False, checked, 0, int(seq), "hash_mismatch", stored_hash, computed
                )
            prev_hash = stored_hash

    blobs = conn.execute(
        "SELECT DISTINCT v.content_hash, coalesce(o.storage_key, b.storage_key) "
        "FROM versions v JOIN blobs b ON b.content_hash = v.content_hash "
        "LEFT JOIN blob_overrides o ON o.tenant_id = v.tenant_id "
        "AND o.content_hash = v.content_hash "
        "WHERE v.tenant_id = %s AND (%s::timestamptz IS NULL OR v.created_at >= %s)",
        (tenant_id, blob_since, blob_since),
    ).fetchall()
    for checked_blobs, (content_hash, key) in enumerate(blobs, start=1):
        try:
            content = store.get(str(key))
        except BlobNotFound:
            return VerifyResult(False, checked, checked_blobs, None, "blob_mismatch")
        if sha256_hex(content) != content_hash:
            return VerifyResult(False, checked, checked_blobs, None, "blob_mismatch")
    return VerifyResult(True, checked, len(blobs), None, None)
