import uuid
from collections.abc import Callable

import psycopg
import pytest
from psycopg import errors

from tests.conftest import LEDGER_TABLES

pytestmark = pytest.mark.integration

HASH = "a" * 64


def _seed_record(conn: psycopg.Connection, tenant: uuid.UUID, actor: uuid.UUID) -> uuid.UUID:
    """Insert a blob, record, version and one event for a tenant (owner connection)."""
    record_id = uuid.uuid4()
    conn.execute(
        "INSERT INTO blobs (content_hash, size_bytes, media_type, storage_key) "
        "VALUES (%s, 2, 'application/json', %s) ON CONFLICT DO NOTHING",
        (HASH, f"blobs/{HASH}"),
    )
    conn.execute(
        "INSERT INTO records (tenant_id, id, kind, subject_ref, created_by) "
        "VALUES (%s, %s, 'patient-summary', 'patient-1', %s)",
        (tenant, record_id, actor),
    )
    conn.execute(
        "INSERT INTO versions (tenant_id, record_id, version_no, content_hash, created_by) "
        "VALUES (%s, %s, 1, %s, %s)",
        (tenant, record_id, HASH, actor),
    )
    conn.execute(
        "INSERT INTO events (tenant_id, seq, event_type, record_id, version_no, actor, "
        "actor_role, occurred_at, payload, prev_hash, event_hash) "
        "VALUES (%s, 1, 'record.created', %s, 1, %s, 'clinician', now(), '{}', %s, %s)",
        (tenant, record_id, actor, "0" * 64, "b" * 64),
    )
    return record_id


def _as_tenant(conn: psycopg.Connection, tenant: uuid.UUID) -> None:
    conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant),))


def test_migration_creates_tables(owner_conn: psycopg.Connection) -> None:
    rows = owner_conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    ).fetchall()
    assert set(LEDGER_TABLES) <= {name for (name,) in rows}


def test_app_role_cannot_update_events(
    app_conn: psycopg.Connection,
    owner_conn: psycopg.Connection,
    make_tenant: Callable[..., uuid.UUID],
    actors: dict[str, uuid.UUID],
) -> None:
    tenant = make_tenant()
    _seed_record(owner_conn, tenant, actors["clinician"])
    _as_tenant(app_conn, tenant)
    with pytest.raises(errors.InsufficientPrivilege):
        app_conn.execute("UPDATE events SET payload = '{}'")


def test_app_role_cannot_delete_versions(
    app_conn: psycopg.Connection,
    owner_conn: psycopg.Connection,
    make_tenant: Callable[..., uuid.UUID],
    actors: dict[str, uuid.UUID],
) -> None:
    tenant = make_tenant()
    _seed_record(owner_conn, tenant, actors["clinician"])
    _as_tenant(app_conn, tenant)
    with pytest.raises(errors.InsufficientPrivilege):
        app_conn.execute("DELETE FROM versions")


def test_trigger_blocks_owner_update_without_maintenance(
    owner_conn: psycopg.Connection,
    make_tenant: Callable[..., uuid.UUID],
    actors: dict[str, uuid.UUID],
) -> None:
    tenant = make_tenant()
    _seed_record(owner_conn, tenant, actors["clinician"])
    with pytest.raises(errors.RaiseException, match="append-only"):
        owner_conn.execute("UPDATE events SET payload = '{}'")


def test_app_role_cannot_unlock_maintenance(
    app_conn: psycopg.Connection,
    owner_conn: psycopg.Connection,
    make_tenant: Callable[..., uuid.UUID],
    actors: dict[str, uuid.UUID],
) -> None:
    tenant_a, tenant_b = make_tenant(), make_tenant()
    _seed_record(owner_conn, tenant_a, actors["clinician"])
    _seed_record(owner_conn, tenant_b, actors["clinician"])
    app_conn.execute("SELECT set_config('ledger.maintenance', 'on', false)")
    _as_tenant(app_conn, tenant_a)
    count = app_conn.execute("SELECT count(*) FROM records").fetchone()
    assert count == (1,)


def test_rls_hides_other_tenants(
    app_conn: psycopg.Connection,
    owner_conn: psycopg.Connection,
    make_tenant: Callable[..., uuid.UUID],
    actors: dict[str, uuid.UUID],
) -> None:
    tenant_a, tenant_b = make_tenant(), make_tenant()
    _seed_record(owner_conn, tenant_a, actors["clinician"])
    _seed_record(owner_conn, tenant_b, actors["clinician"])
    _as_tenant(app_conn, tenant_a)
    for table in ("records", "versions", "record_heads", "events"):
        count = app_conn.execute(f"SELECT count(*) FROM {table}").fetchone()  # noqa: S608
        assert count is not None
        assert count[0] <= 1, table
    assert app_conn.execute("SELECT count(*) FROM records").fetchone() == (1,)


def test_rls_without_tenant_setting_returns_nothing(
    app_conn: psycopg.Connection,
    owner_conn: psycopg.Connection,
    make_tenant: Callable[..., uuid.UUID],
    actors: dict[str, uuid.UUID],
) -> None:
    _seed_record(owner_conn, make_tenant(), actors["clinician"])
    assert app_conn.execute("SELECT count(*) FROM records").fetchone() == (0,)


def test_demo_tamper_event_only_touches_given_tenant(
    app_conn: psycopg.Connection,
    owner_conn: psycopg.Connection,
    make_tenant: Callable[..., uuid.UUID],
    actors: dict[str, uuid.UUID],
) -> None:
    tenant_a, tenant_b = make_tenant(), make_tenant()
    _seed_record(owner_conn, tenant_a, actors["clinician"])
    _seed_record(owner_conn, tenant_b, actors["clinician"])
    _as_tenant(app_conn, tenant_a)
    app_conn.execute("SELECT demo_tamper_event(%s, 1)", (tenant_a,))
    app_conn.commit()
    rows = dict(
        owner_conn.execute(
            "SELECT tenant_id, payload FROM events WHERE seq = 1 AND tenant_id IN (%s, %s)",
            (tenant_a, tenant_b),
        ).fetchall()
    )
    assert rows[tenant_a] == {"tampered": True}
    assert rows[tenant_b] == {}


def test_demo_tamper_event_refuses_other_tenant(
    app_conn: psycopg.Connection,
    owner_conn: psycopg.Connection,
    make_tenant: Callable[..., uuid.UUID],
    actors: dict[str, uuid.UUID],
) -> None:
    tenant_a, tenant_b = make_tenant(), make_tenant()
    _seed_record(owner_conn, tenant_b, actors["clinician"])
    _as_tenant(app_conn, tenant_a)
    with pytest.raises(errors.RaiseException, match="own tenant"):
        app_conn.execute("SELECT demo_tamper_event(%s, 1)", (tenant_b,))


def test_cleanup_removes_only_expired_demo_tenants(
    app_conn: psycopg.Connection,
    owner_conn: psycopg.Connection,
    make_tenant: Callable[..., uuid.UUID],
    actors: dict[str, uuid.UUID],
) -> None:
    expired = make_tenant(kind="demo", expires_in_hours=-1)
    live = make_tenant(kind="demo", expires_in_hours=24)
    standard = make_tenant(kind="standard", expires_in_hours=None)
    for tenant in (expired, live, standard):
        _seed_record(owner_conn, tenant, actors["clinician"])
    removed = app_conn.execute("SELECT cleanup_expired_tenants()").fetchone()
    app_conn.commit()
    assert removed == (1,)
    remaining = {tid for (tid,) in owner_conn.execute("SELECT id FROM tenants").fetchall()}
    assert remaining == {live, standard}
    leftover = owner_conn.execute(
        "SELECT count(*) FROM events WHERE tenant_id = %s", (expired,)
    ).fetchone()
    assert leftover == (0,)
