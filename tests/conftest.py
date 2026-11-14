"""Shared fixtures. Integration tests need PostgreSQL 16 at TEST_DATABASE_URL_OWNER."""

import os
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv

if TYPE_CHECKING:
    from clinical_ledger.settings import Settings

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

LEDGER_TABLES = (
    "tenants",
    "actors",
    "blobs",
    "records",
    "versions",
    "record_heads",
    "events",
    "checkpoints",
    "blob_overrides",
)


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is not set")
    return value


@pytest.fixture(scope="session")
def owner_dsn() -> str:
    dsn = _require("TEST_DATABASE_URL_OWNER")
    database = urlsplit(dsn).path.lstrip("/")
    if not database.endswith("_test"):
        raise RuntimeError(f"refusing to run tests against {database!r}: name must end in _test")
    return dsn


@pytest.fixture(scope="session")
def app_dsn(owner_dsn: str) -> str:
    password = _require("LEDGER_APP_PASSWORD")
    parts = urlsplit(owner_dsn)
    host = parts.hostname or "localhost"
    netloc = f"ledger_app:{quote(password, safe='')}@{host}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


@pytest.fixture(scope="session")
def migrated_db(owner_dsn: str) -> str:
    with psycopg.connect(owner_dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "db" / "migrations"))
    config.attributes["database_url"] = owner_dsn
    command.upgrade(config, "head")
    return owner_dsn


@pytest.fixture
def owner_conn(migrated_db: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(migrated_db, autocommit=True) as conn:
        yield conn


@pytest.fixture
def clean_tables(owner_conn: psycopg.Connection) -> None:
    owner_conn.execute(f"TRUNCATE {', '.join(LEDGER_TABLES)} CASCADE")


@pytest.fixture
def app_conn(app_dsn: str, clean_tables: None) -> Iterator[psycopg.Connection]:
    with psycopg.connect(app_dsn) as conn:
        yield conn


@pytest.fixture
def make_tenant(owner_conn: psycopg.Connection, clean_tables: None) -> Callable[..., uuid.UUID]:
    def _make(kind: str = "demo", expires_in_hours: int | None = 24) -> uuid.UUID:
        tenant_id = uuid.uuid4()
        owner_conn.execute(
            "INSERT INTO tenants (id, name, kind, expires_at) VALUES "
            "(%s, %s, %s, CASE WHEN %s::int IS NULL THEN NULL "
            "ELSE now() + make_interval(hours => %s::int) END)",
            (tenant_id, f"tenant {tenant_id.hex[:6]}", kind, expires_in_hours, expires_in_hours),
        )
        return tenant_id

    return _make


def make_settings(**overrides: object) -> "Settings":
    """Settings for tests: in-memory storage and no real endpoints."""
    from clinical_ledger.settings import Settings

    values: dict[str, object] = {
        "database_url": "postgresql://unused@localhost/unused",
        "s3_backend": "memory",
        "s3_endpoint_url": None,
        "s3_bucket": "clinical-ledger",
        "s3_access_key_id": "test",
        "s3_secret_access_key": "test",
        "s3_region": "us-east-1",
        "jwt_secret": "test-jwt-secret-that-is-long-enough-32b",
        "cron_secret": "test-cron-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg, arg-type]


@pytest.fixture
def settings() -> "Settings":
    return make_settings()


@pytest.fixture
def actors(owner_conn: psycopg.Connection, clean_tables: None) -> dict[str, uuid.UUID]:
    """One actor per role. Replaced by the seed actors once seeding exists."""
    ids = {role: uuid.uuid4() for role in ("clinician", "auditor", "admin")}
    for role, actor_id in ids.items():
        owner_conn.execute(
            "INSERT INTO actors (id, display_name, role) VALUES (%s, %s, %s)",
            (actor_id, f"Demo {role}", role),
        )
    return ids
