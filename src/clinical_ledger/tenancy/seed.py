"""The demo seed set: loading it, installing its shared rows, and demo edits."""

import base64
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

from clinical_ledger.storage.blobs import BlobStore, blob_key

DEFAULT_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "seed.json"


@dataclass(frozen=True)
class SeedActor:
    id: UUID
    display_name: str
    role: str


@dataclass(frozen=True)
class SeedVersion:
    content_hash: str
    media_type: str
    note: str
    created_offset_days: int


@dataclass(frozen=True)
class SeedRecord:
    key: str
    kind: str
    subject_ref: str
    versions: tuple[SeedVersion, ...]


@dataclass(frozen=True)
class DemoEdit:
    description: str
    json_patch: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Seed:
    actors: tuple[SeedActor, ...]
    records: tuple[SeedRecord, ...]
    demo_edits: dict[str, tuple[DemoEdit, ...]]
    blobs: dict[str, bytes]

    def actor_for(self, role: str) -> SeedActor:
        return next(actor for actor in self.actors if actor.role == role)


def parse_seed(data: dict[str, Any]) -> Seed:
    return Seed(
        actors=tuple(
            SeedActor(UUID(a["id"]), a["display_name"], a["role"]) for a in data["actors"]
        ),
        records=tuple(
            SeedRecord(
                key=r["key"],
                kind=r["kind"],
                subject_ref=r["subject_ref"],
                versions=tuple(SeedVersion(**v) for v in r["versions"]),
            )
            for r in data["records"]
        ),
        demo_edits={
            kind: tuple(DemoEdit(e["description"], tuple(e["json_patch"])) for e in edits)
            for kind, edits in data["demo_edits"].items()
        },
        blobs={h: base64.b64decode(b) for h, b in data["blobs"].items()},
    )


@lru_cache
def load_seed(path: Path = DEFAULT_SEED_PATH) -> Seed:
    return parse_seed(json.loads(path.read_text("utf-8")))


def next_edit(seed: Seed, kind: str, version_no: int) -> DemoEdit:
    """The demo edit to apply to a record of `kind` whose latest version is `version_no`."""
    edits = seed.demo_edits[kind]
    return edits[(version_no - 1) % len(edits)]


def install_seed(owner_conn: psycopg.Connection, store: BlobStore, seed: Seed) -> None:
    """Insert the shared actors and seed blobs (owner connection). Safe to re-run."""
    media = {v.content_hash: v.media_type for r in seed.records for v in r.versions}
    for content_hash, content in seed.blobs.items():
        key = blob_key(content_hash)
        if not store.exists(key):
            store.put(key, content, media[content_hash])
    with owner_conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO actors (id, display_name, role) VALUES (%s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING",
            [(a.id, a.display_name, a.role) for a in seed.actors],
        )
        cur.executemany(
            "INSERT INTO blobs (content_hash, size_bytes, media_type, storage_key) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (content_hash) DO NOTHING",
            [
                (content_hash, len(content), media[content_hash], blob_key(content_hash))
                for content_hash, content in seed.blobs.items()
            ],
        )
