import uuid
from collections.abc import Callable
from datetime import timedelta

import psycopg
import pytest

from clinical_ledger.db import tenant_transaction
from clinical_ledger.errors import ContentTampered, RecordNotFound, VersionNotFound
from clinical_ledger.ledger.models import Actor, VersionRef
from clinical_ledger.ledger.reader import LedgerReader
from clinical_ledger.ledger.writer import LedgerWriter
from clinical_ledger.settings import Settings
from clinical_ledger.storage.blobs import InMemoryBlobStore, override_key

pytestmark = pytest.mark.integration

JSON = "application/json"


class Ledger:
    def __init__(
        self, conn: psycopg.Connection, tenant: uuid.UUID, actor: Actor, settings: Settings
    ) -> None:
        self.conn = conn
        self.tenant = tenant
        self.store = InMemoryBlobStore()
        self.writer = LedgerWriter(conn, self.store, tenant, actor, settings)
        self.reader = LedgerReader(conn, self.store, tenant, actor, self.writer)

    def write(self, *contents: bytes, media_type: str = JSON) -> list[VersionRef]:
        refs: list[VersionRef] = []
        for content in contents:
            with tenant_transaction(self.conn, self.tenant):
                if refs:
                    refs.append(self.writer.add_version(refs[0].record_id, content, media_type))
                else:
                    refs.append(
                        self.writer.create_record("lab-panel", "patient-1", content, media_type)
                    )
        return refs


@pytest.fixture
def ledger(
    app_conn: psycopg.Connection,
    make_tenant: Callable[..., uuid.UUID],
    actors: dict[str, uuid.UUID],
    settings: Settings,
) -> Ledger:
    return Ledger(app_conn, make_tenant(), Actor(actors["clinician"], "clinician"), settings)


def _event_types(owner: psycopg.Connection, tenant: uuid.UUID) -> list[str]:
    rows = owner.execute(
        "SELECT event_type FROM events WHERE tenant_id = %s ORDER BY seq", (tenant,)
    ).fetchall()
    return [event_type for (event_type,) in rows]


def test_latest_returns_newest_and_logs_read_event(
    ledger: Ledger, owner_conn: psycopg.Connection
) -> None:
    refs = ledger.write(b'{"v":1}', b'{"v":2}')
    with tenant_transaction(ledger.conn, ledger.tenant):
        result = ledger.reader.latest(refs[0].record_id)
    assert result.ref.version_no == 2
    assert result.content == b'{"v":2}'
    assert result.media_type == JSON
    assert _event_types(owner_conn, ledger.tenant)[-1] == "record.read"


def test_latest_unknown_record_raises(ledger: Ledger) -> None:
    with pytest.raises(RecordNotFound), tenant_transaction(ledger.conn, ledger.tenant):
        ledger.reader.latest(uuid.uuid4())


def test_version_returns_exact_bytes(ledger: Ledger, owner_conn: psycopg.Connection) -> None:
    refs = ledger.write(b'{"v":1}', b'{"v":2}', b'{"v":3}')
    with tenant_transaction(ledger.conn, ledger.tenant):
        result = ledger.reader.version(refs[0].record_id, 2)
    assert result.content == b'{"v":2}'
    assert _event_types(owner_conn, ledger.tenant)[-1] == "version.read"


def test_version_missing_raises(ledger: Ledger) -> None:
    refs = ledger.write(b'{"v":1}')
    with pytest.raises(VersionNotFound), tenant_transaction(ledger.conn, ledger.tenant):
        ledger.reader.version(refs[0].record_id, 9)


def test_as_of_returns_version_current_at_time(ledger: Ledger) -> None:
    refs = ledger.write(b'{"v":1}', b'{"v":2}', b'{"v":3}')
    with tenant_transaction(ledger.conn, ledger.tenant):
        result = ledger.reader.as_of(refs[0].record_id, refs[1].created_at)
    assert result.ref.version_no == 2


def test_as_of_before_record_existed_raises_version_not_found(ledger: Ledger) -> None:
    refs = ledger.write(b'{"v":1}')
    with pytest.raises(VersionNotFound), tenant_transaction(ledger.conn, ledger.tenant):
        ledger.reader.as_of(refs[0].record_id, refs[0].created_at - timedelta(days=1))


def test_list_versions_ordered(ledger: Ledger) -> None:
    refs = ledger.write(b'{"v":1}', b'{"v":2}', b'{"v":3}')
    with tenant_transaction(ledger.conn, ledger.tenant):
        versions = ledger.reader.list_versions(refs[0].record_id)
    assert [v.version_no for v in versions] == [1, 2, 3]


def test_list_records_paginates(ledger: Ledger) -> None:
    for _ in range(3):
        ledger.write(b'{"v":1}')
    with tenant_transaction(ledger.conn, ledger.tenant):
        first = ledger.reader.list_records(limit=2, cursor=None)
        rest = ledger.reader.list_records(limit=2, cursor=first[-1].id)
    assert len(first) == 2
    assert len(rest) == 1
    assert rest[0].id not in {r.id for r in first}
    assert first[0].latest_version_no == 1


def test_diff_json_returns_patch_ops(ledger: Ledger) -> None:
    refs = ledger.write(b'{"status":"preliminary"}', b'{"status":"final"}')
    with tenant_transaction(ledger.conn, ledger.tenant):
        ops = ledger.reader.diff(refs[0].record_id, 1, 2)
    assert ops == [{"op": "replace", "path": "/status", "value": "final"}]


def test_diff_binary_reports_hashes(ledger: Ledger) -> None:
    refs = ledger.write(b"\x00\x01", b"\x00\x01\x02", media_type="application/pdf")
    with tenant_transaction(ledger.conn, ledger.tenant):
        ops = ledger.reader.diff(refs[0].record_id, 1, 2)
    assert ops == [
        {
            "op": "binary",
            "from_hash": refs[0].content_hash,
            "to_hash": refs[1].content_hash,
            "from_size": 2,
            "to_size": 3,
        }
    ]


def test_read_detects_overridden_blob(ledger: Ledger) -> None:
    refs = ledger.write(b'{"v":1}')
    key = override_key(ledger.tenant, refs[0].content_hash)
    ledger.store.put(key, b'{"v":999}', JSON)
    with tenant_transaction(ledger.conn, ledger.tenant):
        ledger.conn.execute(
            "INSERT INTO blob_overrides (tenant_id, content_hash, storage_key) VALUES (%s, %s, %s)",
            (ledger.tenant, refs[0].content_hash, key),
        )
    with pytest.raises(ContentTampered), tenant_transaction(ledger.conn, ledger.tenant):
        ledger.reader.latest(refs[0].record_id)
