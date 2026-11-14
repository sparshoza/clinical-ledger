"""Demo tenants: one private, short-lived ledger per visitor, copied from the seed set."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from clinical_ledger.db import tenant_transaction
from clinical_ledger.ledger.hashing import GENESIS_HASH, compute_event_hash, event_hash_fields
from clinical_ledger.settings import Settings
from clinical_ledger.tenancy.seed import Seed


def tenant_exists(conn: psycopg.Connection, tenant_id: UUID) -> bool:
    row = conn.execute("SELECT 1 FROM tenants WHERE id = %s", (tenant_id,)).fetchone()
    return row is not None


def create_demo_tenant(conn: psycopg.Connection, settings: Settings, seed: Seed) -> UUID:
    """Create a demo tenant holding a fresh copy of the seed records and its own chain.

    Blobs are shared and must already be installed (`install_seed`).
    """
    tenant_id = uuid.uuid4()
    now = datetime.now(UTC)
    author = seed.actor_for("clinician")

    records: list[tuple[Any, ...]] = []
    versions: list[tuple[Any, ...]] = []
    heads: list[tuple[Any, ...]] = []
    timeline: list[tuple[datetime, int, int, UUID, str, str]] = []
    for order, record in enumerate(seed.records):
        record_id = uuid.uuid4()
        stamps = [now + timedelta(days=v.created_offset_days) for v in record.versions]
        records.append(
            (tenant_id, record_id, record.kind, record.subject_ref, stamps[0], author.id)
        )
        for number, (version, stamp) in enumerate(zip(record.versions, stamps, strict=True), 1):
            versions.append(
                (tenant_id, record_id, number, version.content_hash, stamp, author.id, version.note)
            )
            event_type = "record.created" if number == 1 else "version.added"
            timeline.append((stamp, order, number, record_id, event_type, version.content_hash))
        last = record.versions[-1]
        heads.append((tenant_id, record_id, len(record.versions), last.content_hash, stamps[-1]))
    kinds = {r[1]: r[2] for r in records}

    events: list[tuple[Any, ...]] = []
    checkpoints: list[tuple[Any, ...]] = []
    prev_hash = GENESIS_HASH
    for seq, (stamp, _order, number, record_id, event_type, content_hash) in enumerate(
        sorted(timeline, key=lambda item: (item[0], item[1], item[2])), start=1
    ):
        payload: dict[str, Any] = {"content_hash": content_hash}
        if event_type == "record.created":
            payload["kind"] = kinds[record_id]
        fields = event_hash_fields(
            tenant_id=tenant_id,
            seq=seq,
            event_type=event_type,
            record_id=record_id,
            version_no=number,
            actor=author.id,
            actor_role=author.role,
            occurred_at=stamp,
            payload=payload,
        )
        event_hash = compute_event_hash(prev_hash, fields)
        events.append(
            (
                tenant_id,
                seq,
                event_type,
                record_id,
                number,
                author.id,
                author.role,
                stamp,
                Jsonb(payload),
                prev_hash,
                event_hash,
            )
        )
        if seq % settings.checkpoint_interval == 0:
            checkpoints.append((tenant_id, seq, event_hash))
        prev_hash = event_hash

    with tenant_transaction(conn, tenant_id), conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, name, kind, created_at, expires_at) "
            "VALUES (%s, %s, 'demo', %s, %s)",
            (
                tenant_id,
                f"Demo {tenant_id.hex[:8]}",
                now,
                now + timedelta(hours=settings.demo_tenant_ttl_hours),
            ),
        )
        cur.executemany(
            "INSERT INTO records (tenant_id, id, kind, subject_ref, created_at, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            records,
        )
        cur.executemany(
            "INSERT INTO versions (tenant_id, record_id, version_no, content_hash, created_at, "
            "created_by, note) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            versions,
        )
        cur.executemany(
            "INSERT INTO record_heads (tenant_id, record_id, latest_version_no, "
            "latest_content_hash, updated_at) VALUES (%s, %s, %s, %s, %s)",
            heads,
        )
        cur.executemany(
            "INSERT INTO events (tenant_id, seq, event_type, record_id, version_no, actor, "
            "actor_role, occurred_at, payload, prev_hash, event_hash) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            events,
        )
        if checkpoints:
            cur.executemany(
                "INSERT INTO checkpoints (tenant_id, seq, event_hash) VALUES (%s, %s, %s)",
                checkpoints,
            )
    return tenant_id
