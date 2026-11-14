import uuid
from collections.abc import Callable

import psycopg
import pytest

from clinical_ledger.db import tenant_transaction
from clinical_ledger.ledger.models import Actor
from clinical_ledger.ledger.verify import verify_chain
from clinical_ledger.ledger.writer import LedgerWriter
from clinical_ledger.settings import Settings
from clinical_ledger.storage.blobs import InMemoryBlobStore, override_key
from tests.conftest import make_settings

pytestmark = pytest.mark.integration

JSON = "application/json"


@pytest.fixture
def clinician(actors: dict[str, uuid.UUID]) -> Actor:
    return Actor(actors["clinician"], "clinician")


@pytest.fixture
def store() -> InMemoryBlobStore:
    return InMemoryBlobStore()


def _fill(
    conn: psycopg.Connection,
    store: InMemoryBlobStore,
    tenant: uuid.UUID,
    actor: Actor,
    settings: Settings,
    versions: int = 3,
) -> uuid.UUID:
    writer = LedgerWriter(conn, store, tenant, actor, settings)
    with tenant_transaction(conn, tenant):
        ref = writer.create_record(
            "patient-summary",
            "patient-1",
            '{"name":"José","address":{"city":"Orlando","lines":["1 Main St"]}}'.encode(),
            JSON,
        )
        for n in range(2, versions + 1):
            writer.add_version(ref.record_id, f'{{"name":"José","v":{n}}}'.encode(), JSON)
        writer.append_event(
            "note.added",
            ref.record_id,
            None,
            {"note": "Ünïcödé ✓", "nested": {"b": 1, "a": [True, None]}},
        )
    return ref.record_id


def _verify(conn: psycopg.Connection, store: InMemoryBlobStore, tenant: uuid.UUID, **kw: bool):  # type: ignore[no-untyped-def]
    with tenant_transaction(conn, tenant):
        return verify_chain(conn, store, tenant, **kw)


def test_intact_chain_verifies(
    app_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    make_tenant: Callable[..., uuid.UUID],
    clinician: Actor,
    settings: Settings,
) -> None:
    tenant = make_tenant()
    _fill(app_conn, store, tenant, clinician, settings)
    result = _verify(app_conn, store, tenant)
    assert result.ok
    assert result.checked_events == 4
    assert result.checked_blobs == 3
    assert result.first_broken_seq is None
    assert result.reason is None


def test_verify_ignores_session_time_zone(
    app_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    make_tenant: Callable[..., uuid.UUID],
    clinician: Actor,
    settings: Settings,
) -> None:
    tenant = make_tenant()
    _fill(app_conn, store, tenant, clinician, settings)
    app_conn.execute("SET TIME ZONE 'Asia/Kolkata'")
    app_conn.commit()
    assert _verify(app_conn, store, tenant).ok


def test_tampered_event_reports_its_seq(
    app_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    make_tenant: Callable[..., uuid.UUID],
    clinician: Actor,
    settings: Settings,
) -> None:
    tenant = make_tenant()
    _fill(app_conn, store, tenant, clinician, settings, versions=9)
    with tenant_transaction(app_conn, tenant):
        app_conn.execute("SELECT demo_tamper_event(%s, 7)", (tenant,))
    result = _verify(app_conn, store, tenant)
    assert result.ok is False
    assert result.first_broken_seq == 7
    assert result.reason == "hash_mismatch"


def test_override_blob_reports_blob_mismatch(
    app_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    make_tenant: Callable[..., uuid.UUID],
    clinician: Actor,
    settings: Settings,
) -> None:
    tenant = make_tenant()
    _fill(app_conn, store, tenant, clinician, settings)
    with tenant_transaction(app_conn, tenant):
        content_hash = app_conn.execute(
            "SELECT content_hash FROM versions WHERE tenant_id = %s ORDER BY version_no LIMIT 1",
            (tenant,),
        ).fetchone()[0]  # type: ignore[index]
        key = override_key(tenant, content_hash)
        store.put(key, b'{"altered":true}', JSON)
        app_conn.execute(
            "INSERT INTO blob_overrides (tenant_id, content_hash, storage_key) VALUES (%s, %s, %s)",
            (tenant, content_hash, key),
        )
    result = _verify(app_conn, store, tenant)
    assert result.ok is False
    assert result.reason == "blob_mismatch"
    assert result.first_broken_seq is None


def test_from_checkpoint_checks_only_tail(
    app_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    make_tenant: Callable[..., uuid.UUID],
    clinician: Actor,
) -> None:
    tenant = make_tenant()
    _fill(app_conn, store, tenant, clinician, make_settings(checkpoint_interval=5), versions=11)
    result = _verify(app_conn, store, tenant, from_checkpoint=True)
    assert result.ok
    assert result.checked_events == 2


def test_verify_is_tenant_scoped(
    app_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    make_tenant: Callable[..., uuid.UUID],
    clinician: Actor,
    settings: Settings,
) -> None:
    tenant_a, tenant_b = make_tenant(), make_tenant()
    _fill(app_conn, store, tenant_a, clinician, settings)
    _fill(app_conn, store, tenant_b, clinician, settings)
    with tenant_transaction(app_conn, tenant_b):
        app_conn.execute("SELECT demo_tamper_event(%s, 2)", (tenant_b,))
    assert _verify(app_conn, store, tenant_a).ok
    assert not _verify(app_conn, store, tenant_b).ok
