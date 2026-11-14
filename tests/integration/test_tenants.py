import os
import time
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from clinical_ledger.db import tenant_transaction
from clinical_ledger.ledger.verify import verify_chain
from clinical_ledger.settings import Settings
from clinical_ledger.storage.blobs import InMemoryBlobStore
from clinical_ledger.tenancy.seed import Seed, install_seed, load_seed
from clinical_ledger.tenancy.tenants import create_demo_tenant, tenant_exists

pytestmark = pytest.mark.integration


@pytest.fixture
def seed() -> Seed:
    return load_seed()


@pytest.fixture
def store() -> InMemoryBlobStore:
    return InMemoryBlobStore()


@pytest.fixture
def installed(
    owner_conn: psycopg.Connection, clean_tables: None, store: InMemoryBlobStore, seed: Seed
) -> None:
    install_seed(owner_conn, store, seed)


def test_install_seed_is_idempotent(
    owner_conn: psycopg.Connection, installed: None, store: InMemoryBlobStore, seed: Seed
) -> None:
    install_seed(owner_conn, store, seed)
    assert owner_conn.execute("SELECT count(*) FROM actors").fetchone() == (3,)
    assert owner_conn.execute("SELECT count(*) FROM blobs").fetchone() == (len(seed.blobs),)


def test_create_demo_tenant_counts(
    app_conn: psycopg.Connection, installed: None, seed: Seed, settings: Settings
) -> None:
    tenant = create_demo_tenant(app_conn, settings, seed)
    expected_versions = sum(len(r.versions) for r in seed.records)
    with tenant_transaction(app_conn, tenant):
        counts = app_conn.execute(
            "SELECT (SELECT count(*) FROM records), (SELECT count(*) FROM versions), "
            "(SELECT count(*) FROM record_heads), (SELECT count(*) FROM events)"
        ).fetchone()
    assert counts == (75, expected_versions, 75, expected_versions)


def test_new_tenant_chain_verifies(
    app_conn: psycopg.Connection,
    installed: None,
    store: InMemoryBlobStore,
    seed: Seed,
    settings: Settings,
) -> None:
    tenant = create_demo_tenant(app_conn, settings, seed)
    with tenant_transaction(app_conn, tenant):
        result = verify_chain(app_conn, store, tenant)
    assert result.ok, result


def test_demo_tenant_expires_in_24_hours(
    app_conn: psycopg.Connection, installed: None, seed: Seed, settings: Settings
) -> None:
    tenant = create_demo_tenant(app_conn, settings, seed)
    row = app_conn.execute(
        "SELECT kind, expires_at FROM tenants WHERE id = %s", (tenant,)
    ).fetchone()
    assert row is not None
    assert row[0] == "demo"
    expected = datetime.now(UTC) + timedelta(hours=24)
    assert abs(row[1] - expected) < timedelta(minutes=1)
    assert tenant_exists(app_conn, tenant)


@pytest.mark.skipif(bool(os.environ.get("CI_SLOW")), reason="timing is not meaningful here")
def test_create_demo_tenant_under_one_second_locally(
    app_conn: psycopg.Connection, installed: None, seed: Seed, settings: Settings
) -> None:
    started = time.perf_counter()
    create_demo_tenant(app_conn, settings, seed)
    assert time.perf_counter() - started < 1.0
