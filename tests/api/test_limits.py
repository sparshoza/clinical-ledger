from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from clinical_ledger.main import create_app
from clinical_ledger.settings import Settings
from clinical_ledger.storage import blobs
from clinical_ledger.storage.blobs import make_blob_store
from clinical_ledger.tenancy.seed import install_seed, load_seed
from tests.api.conftest import bearer

pytestmark = pytest.mark.integration


@pytest.fixture
def limited(
    api_settings: Settings, owner_conn: psycopg.Connection, clean_tables: None
) -> Iterator[TestClient]:
    settings = api_settings.model_copy(
        update={"demo_signups_per_hour": 2, "max_new_versions_per_tenant": 1}
    )
    install_seed(owner_conn, make_blob_store(settings), load_seed())
    with TestClient(create_app(settings)) as client:
        yield client


def _sign_in(client: TestClient, token: str | None = None, ip: str = "203.0.113.7") -> Any:
    headers = {"X-Forwarded-For": f"{ip}, 10.0.0.1"}
    if token:
        headers |= bearer(token)
    return client.post("/api/v1/auth/demo", json={"role": "admin"}, headers=headers)


def test_new_demo_ledgers_are_limited_per_visitor(limited: TestClient) -> None:
    first = _sign_in(limited)
    assert _sign_in(limited).status_code == 200
    third = _sign_in(limited)
    assert third.status_code == 429
    assert third.headers["content-type"].startswith("application/problem+json")
    # Switching role keeps the same ledger, so it never counts against the limit.
    assert _sign_in(limited, token=first.json()["token"]).status_code == 200
    # Another visitor is unaffected.
    assert _sign_in(limited, ip="198.51.100.9").status_code == 200


def test_visitor_addresses_are_not_stored(
    limited: TestClient, owner_conn: psycopg.Connection
) -> None:
    _sign_in(limited)
    rows = owner_conn.execute("SELECT client_hash FROM demo_signups").fetchall()
    assert rows and all("203.0.113.7" not in row[0] for row in rows)


def test_new_versions_per_ledger_are_capped(limited: TestClient) -> None:
    token = _sign_in(limited).json()["token"]
    record = limited.get("/api/v1/records", headers=bearer(token)).json()["items"][0]["id"]
    assert (
        limited.post(f"/api/v1/records/{record}/demo-edit", headers=bearer(token)).status_code
        == 201
    )
    capped = limited.post(f"/api/v1/records/{record}/demo-edit", headers=bearer(token))
    assert capped.status_code == 429


def test_cleanup_deletes_expired_tampered_files(
    limited: TestClient, owner_conn: psycopg.Connection
) -> None:
    session = _sign_in(limited).json()
    assert (
        limited.post(
            "/api/v1/demo/tamper", json={"mode": "blob"}, headers=bearer(session["token"])
        ).status_code
        == 200
    )
    store = blobs._memory_store
    assert store is not None
    prefix = f"overrides/{session['tenant_id']}/"
    assert any(key.startswith(prefix) for key in store._objects)
    owner_conn.execute("UPDATE tenants SET expires_at = now() - interval '1 minute'")
    response = limited.get(
        "/api/v1/cron/cleanup", headers={"Authorization": "Bearer test-cron-secret"}
    )
    assert response.json() == {"removed": 1}
    assert not any(key.startswith(prefix) for key in store._objects)
