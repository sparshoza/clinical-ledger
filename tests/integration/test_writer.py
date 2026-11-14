import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, tzinfo

import psycopg
import pytest

from clinical_ledger.db import tenant_transaction
from clinical_ledger.errors import ContentTooLarge, RecordNotFound
from clinical_ledger.ledger.hashing import GENESIS_HASH
from clinical_ledger.ledger.models import Actor
from clinical_ledger.ledger.writer import LedgerWriter, chain_lock_key
from clinical_ledger.settings import Settings
from clinical_ledger.storage.blobs import InMemoryBlobStore, blob_key
from tests.conftest import make_settings

pytestmark = pytest.mark.integration

JSON = "application/json"


@pytest.fixture
def tenant(make_tenant: Callable[..., uuid.UUID]) -> uuid.UUID:
    return make_tenant()


@pytest.fixture
def clinician(actors: dict[str, uuid.UUID]) -> Actor:
    return Actor(id=actors["clinician"], role="clinician")


@pytest.fixture
def store() -> InMemoryBlobStore:
    return InMemoryBlobStore()


def _writer(
    conn: psycopg.Connection,
    store: InMemoryBlobStore,
    tenant: uuid.UUID,
    actor: Actor,
    settings: Settings,
) -> LedgerWriter:
    return LedgerWriter(conn, store, tenant, actor, settings)


def _events(owner: psycopg.Connection, tenant: uuid.UUID) -> list[tuple[int, str, str]]:
    return owner.execute(
        "SELECT seq, prev_hash, event_hash FROM events WHERE tenant_id = %s ORDER BY seq",
        (tenant,),
    ).fetchall()


def test_chain_lock_key_is_signed_int64_from_first_8_bytes() -> None:
    tenant = uuid.UUID("ffffffff-ffff-ffff-0000-000000000000")
    assert chain_lock_key(tenant) == -1


def test_create_record_starts_at_version_1_and_sets_head(
    app_conn: psycopg.Connection,
    owner_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    tenant: uuid.UUID,
    clinician: Actor,
    settings: Settings,
) -> None:
    with tenant_transaction(app_conn, tenant):
        ref = _writer(app_conn, store, tenant, clinician, settings).create_record(
            "patient-summary", "patient-1", b'{"status":"preliminary"}', JSON
        )
    assert ref.version_no == 1
    head = owner_conn.execute(
        "SELECT latest_version_no, latest_content_hash FROM record_heads "
        "WHERE tenant_id = %s AND record_id = %s",
        (tenant, ref.record_id),
    ).fetchone()
    assert head == (1, ref.content_hash)
    assert store.get(blob_key(ref.content_hash)) == b'{"status":"preliminary"}'


def test_add_version_increments_and_updates_head(
    app_conn: psycopg.Connection,
    owner_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    tenant: uuid.UUID,
    clinician: Actor,
    settings: Settings,
) -> None:
    writer = _writer(app_conn, store, tenant, clinician, settings)
    with tenant_transaction(app_conn, tenant):
        first = writer.create_record("lab-panel", "patient-1", b'{"v":1}', JSON)
    with tenant_transaction(app_conn, tenant):
        second = writer.add_version(first.record_id, b'{"v":2}', JSON, note="new result")
    assert second.version_no == 2
    head = owner_conn.execute(
        "SELECT latest_version_no FROM record_heads WHERE record_id = %s", (first.record_id,)
    ).fetchone()
    assert head == (2,)


def test_events_link_prev_hash(
    app_conn: psycopg.Connection,
    owner_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    tenant: uuid.UUID,
    clinician: Actor,
    settings: Settings,
) -> None:
    writer = _writer(app_conn, store, tenant, clinician, settings)
    with tenant_transaction(app_conn, tenant):
        ref = writer.create_record("lab-panel", "patient-1", b'{"v":1}', JSON)
        writer.add_version(ref.record_id, b'{"v":2}', JSON)
        writer.add_version(ref.record_id, b'{"v":3}', JSON)
    events = _events(owner_conn, tenant)
    assert [seq for seq, _, _ in events] == [1, 2, 3]
    assert events[0][1] == GENESIS_HASH
    for previous, current in zip(events, events[1:], strict=False):
        assert current[1] == previous[2]


def test_identical_content_stored_once(
    app_conn: psycopg.Connection,
    owner_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    tenant: uuid.UUID,
    clinician: Actor,
    settings: Settings,
) -> None:
    writer = _writer(app_conn, store, tenant, clinician, settings)
    with tenant_transaction(app_conn, tenant):
        writer.create_record("lab-panel", "patient-1", b'{"same":true}', JSON)
        writer.create_record("lab-panel", "patient-2", b'{"same":true}', JSON)
    assert owner_conn.execute("SELECT count(*) FROM blobs").fetchone() == (1,)


def test_content_over_limit_raises(
    app_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    tenant: uuid.UUID,
    clinician: Actor,
    settings: Settings,
) -> None:
    writer = _writer(app_conn, store, tenant, clinician, settings)
    with pytest.raises(ContentTooLarge), tenant_transaction(app_conn, tenant):
        writer.create_record("file", "patient-1", b"x" * 2_097_153, "application/pdf")


def test_add_version_unknown_record_raises(
    app_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    tenant: uuid.UUID,
    clinician: Actor,
    settings: Settings,
) -> None:
    writer = _writer(app_conn, store, tenant, clinician, settings)
    with pytest.raises(RecordNotFound), tenant_transaction(app_conn, tenant):
        writer.add_version(uuid.uuid4(), b"{}", JSON)


def test_concurrent_add_version_never_forks_chain(
    app_conn: psycopg.Connection,
    app_dsn: str,
    owner_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    tenant: uuid.UUID,
    clinician: Actor,
    settings: Settings,
) -> None:
    with tenant_transaction(app_conn, tenant):
        ref = _writer(app_conn, store, tenant, clinician, settings).create_record(
            "lab-panel", "patient-1", b'{"n":0}', JSON
        )
    errors: list[BaseException] = []

    def work(worker: int) -> None:
        try:
            with psycopg.connect(app_dsn) as conn:
                writer = _writer(conn, store, tenant, clinician, settings)
                for i in range(10):
                    with tenant_transaction(conn, tenant):
                        writer.add_version(
                            ref.record_id, f'{{"w":{worker},"i":{i}}}'.encode(), JSON
                        )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    versions = [
        n
        for (n,) in owner_conn.execute(
            "SELECT version_no FROM versions WHERE record_id = %s ORDER BY version_no",
            (ref.record_id,),
        ).fetchall()
    ]
    assert versions == list(range(1, 82))
    events = _events(owner_conn, tenant)
    assert [seq for seq, _, _ in events] == list(range(1, 82))
    for previous, current in zip(events, events[1:], strict=False):
        assert current[1] == previous[2]


def test_checkpoint_written_every_interval(
    app_conn: psycopg.Connection,
    owner_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    tenant: uuid.UUID,
    clinician: Actor,
) -> None:
    writer = _writer(app_conn, store, tenant, clinician, make_settings(checkpoint_interval=5))
    with tenant_transaction(app_conn, tenant):
        ref = writer.create_record("lab-panel", "patient-1", b'{"i":0}', JSON)
        for i in range(1, 12):
            writer.add_version(ref.record_id, f'{{"i":{i}}}'.encode(), JSON)
    seqs = [
        seq
        for (seq,) in owner_conn.execute(
            "SELECT seq FROM checkpoints WHERE tenant_id = %s ORDER BY seq", (tenant,)
        ).fetchall()
    ]
    assert seqs == [5, 10]


def test_versions_of_a_record_get_strictly_increasing_times_on_a_coarse_clock(
    app_conn: psycopg.Connection,
    store: InMemoryBlobStore,
    tenant: uuid.UUID,
    clinician: Actor,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Two writes inside one clock tick must not share a timestamp, or "as of" a version's
    # own time would return the version after it.
    frozen = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)

    class FrozenClock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> "FrozenClock":  # type: ignore[override]
            return cls.fromtimestamp(frozen.timestamp(), tz)

    monkeypatch.setattr("clinical_ledger.ledger.writer.datetime", FrozenClock)
    writer = _writer(app_conn, store, tenant, clinician, settings)
    with tenant_transaction(app_conn, tenant):
        first = writer.create_record("lab-panel", "patient-1", b'{"v":1}', JSON)
    refs = [first]
    for n in (2, 3):
        with tenant_transaction(app_conn, tenant):
            refs.append(writer.add_version(first.record_id, f'{{"v":{n}}}'.encode(), JSON))
    times = [ref.created_at for ref in refs]
    assert times == sorted(times)
    assert len(set(times)) == 3
