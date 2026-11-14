"""Bulk-load one large tenant: a single hash chain of N events over M versions.

Usage: python -m bench.load [--events 2000000] [--versions 500000]
Creates (or recreates) the database `clinical_ledger_bench` next to DATABASE_URL_OWNER,
migrates it, and streams every table in with COPY (nothing large is held in memory).
Three probe records have exactly 1, 100 and 10,000 versions; the rest have 10 each.
Events beyond the version events are record.read entries, as a busy clinic produces.
"""

import argparse
import json
import os
import time
import uuid
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

from bench.content import content_for
from clinical_ledger.ledger.hashing import (
    GENESIS_HASH,
    compute_event_hash,
    event_hash_fields,
    sha256_hex,
)
from clinical_ledger.storage.blobs import blob_key

ROOT = Path(__file__).resolve().parent.parent
INFO_PATH = ROOT / "bench" / "results" / "loaded.json"
BENCH_DB = "clinical_ledger_bench"
PROBES = (1, 100, 10_000)
CHECKPOINT_INTERVAL = 1000
BASE = datetime(2026, 1, 1, tzinfo=UTC)
TICK = timedelta(milliseconds=1)


@dataclass
class BenchInfo:
    owner_dsn: str
    tenant_id: str
    actor_id: str
    events: int
    versions: int
    record_count: int
    probe_records: dict[str, str]  # version count -> record id
    load_seconds: float


def record_plan(versions: int) -> list[int]:
    """Version count per record: the probes that fit, then records of 10, then the rest."""
    plan = [p for p in PROBES if p <= versions // 4] or [1]
    remaining = versions - sum(plan)
    plan += [10] * (remaining // 10)
    if remaining % 10:
        plan.append(remaining % 10)
    return plan


def load(owner_dsn: str, events: int, versions: int) -> BenchInfo:
    if events < versions:
        raise ValueError("events must be at least versions")
    started = time.perf_counter()
    tenant_id, actor_id = uuid.uuid4(), uuid.uuid4()
    plan = record_plan(versions)
    record_ids = [uuid.uuid4() for _ in plan]
    hashes = [[sha256_hex(content_for(i, v)) for v in range(1, n + 1)] for i, n in enumerate(plan)]

    def version_rows() -> Iterator[tuple[int, int, int, str]]:
        """(event seq, record index, version, hash) in chain order."""
        seq = 0
        for index, record_hashes in enumerate(hashes):
            for version, content_hash in enumerate(record_hashes, start=1):
                seq += 1
                yield seq, index, version, content_hash

    checkpoints: list[tuple[Any, ...]] = []

    def event_rows() -> Iterator[tuple[Any, ...]]:
        prev_hash = GENESIS_HASH
        stream: Iterator[tuple[int, int, int, str | None]] = version_rows()
        total_versions = sum(plan)

        def reads() -> Iterator[tuple[int, int, int, str | None]]:
            for n in range(events - total_versions):
                index = (n * 7919) % len(plan)
                yield total_versions + n + 1, index, plan[index], None

        for source in (stream, reads()):
            for seq, index, version, content_hash in source:
                if content_hash is None:
                    event_type, payload = "record.read", {}
                else:
                    event_type = "record.created" if version == 1 else "version.added"
                    payload = {"content_hash": content_hash}
                at = BASE + TICK * seq
                fields = event_hash_fields(
                    tenant_id=tenant_id,
                    seq=seq,
                    event_type=event_type,
                    record_id=record_ids[index],
                    version_no=version,
                    actor=actor_id,
                    actor_role="clinician",
                    occurred_at=at,
                    payload=payload,
                )
                event_hash = compute_event_hash(prev_hash, fields)
                if seq % CHECKPOINT_INTERVAL == 0:
                    checkpoints.append((tenant_id, seq, event_hash))
                yield (
                    tenant_id,
                    seq,
                    event_type,
                    record_ids[index],
                    version,
                    actor_id,
                    "clinician",
                    at,
                    Jsonb(payload),
                    prev_hash,
                    event_hash,
                )
                prev_hash = event_hash

    tables: list[tuple[str, str, Iterator[tuple[Any, ...]]]] = [
        (
            "blobs",
            "content_hash, size_bytes, media_type, storage_key",
            (
                (h, len(content_for(i, v)), "application/json", blob_key(h))
                for _, i, v, h in version_rows()
            ),
        ),
        (
            "records",
            "tenant_id, id, kind, subject_ref, created_at, created_by",
            (
                (tenant_id, record_ids[i], "lab-panel", f"Patient/bench-{i}", BASE, actor_id)
                for i in range(len(plan))
            ),
        ),
        (
            "versions",
            "tenant_id, record_id, version_no, content_hash, created_at, created_by, note",
            (
                (tenant_id, record_ids[i], v, h, BASE + TICK * s, actor_id, "")
                for s, i, v, h in version_rows()
            ),
        ),
        (
            "record_heads",
            "tenant_id, record_id, latest_version_no, latest_content_hash, updated_at",
            (
                (tenant_id, record_ids[i], v, h, BASE + TICK * s)
                for s, i, v, h in version_rows()
                if v == plan[i]
            ),
        ),
        (
            "events",
            "tenant_id, seq, event_type, record_id, version_no, actor, actor_role, "
            "occurred_at, payload, prev_hash, event_hash",
            event_rows(),
        ),
    ]
    with psycopg.connect(owner_dsn, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO tenants (id, name, kind) VALUES (%s, 'Benchmark', 'standard')",
            (tenant_id,),
        )
        conn.execute(
            "INSERT INTO actors (id, display_name, role) VALUES (%s, 'Benchmark writer', "
            "'clinician')",
            (actor_id,),
        )
        with conn.cursor() as cur:
            for table, columns, rows in tables:
                with cur.copy(f"COPY {table} ({columns}) FROM STDIN") as copy:  # noqa: S608
                    for row in rows:
                        copy.write_row(row)
            with cur.copy("COPY checkpoints (tenant_id, seq, event_hash) FROM STDIN") as copy:
                for row in checkpoints:
                    copy.write_row(row)
        conn.execute("ANALYZE")

    return BenchInfo(
        owner_dsn=owner_dsn,
        tenant_id=str(tenant_id),
        actor_id=str(actor_id),
        events=events,
        versions=sum(plan),
        record_count=len(plan),
        probe_records={
            str(n): str(record_ids[i])
            for i, n in enumerate(plan)
            if n in PROBES and i < len(PROBES)
        },
        load_seconds=round(time.perf_counter() - started, 1),
    )


def bench_owner_dsn() -> str:
    load_dotenv(ROOT / ".env")
    return os.environ["DATABASE_URL_OWNER"].rsplit("/", 1)[0] + f"/{BENCH_DB}"


def recreate_database(owner_dsn: str) -> None:
    admin = owner_dsn.rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{BENCH_DB}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{BENCH_DB}"')
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = owner_dsn
    command.upgrade(config, "head")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=2_000_000)
    parser.add_argument("--versions", type=int, default=500_000)
    args = parser.parse_args()
    owner_dsn = bench_owner_dsn()
    recreate_database(owner_dsn)
    info = load(owner_dsn, args.events, args.versions)
    INFO_PATH.parent.mkdir(parents=True, exist_ok=True)
    INFO_PATH.write_text(json.dumps(asdict(info), indent=2), "utf-8")
    print(f"loaded {info.events} events, {info.versions} versions in {info.load_seconds}s")


if __name__ == "__main__":
    main()
