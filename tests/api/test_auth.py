from collections.abc import Callable

import psycopg
import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import bearer

pytestmark = pytest.mark.integration

SignIn = Callable[..., dict[str, str]]


def test_demo_sign_in_creates_tenant(sign_in: SignIn, owner_conn: psycopg.Connection) -> None:
    body = sign_in("clinician")
    assert body["role"] == "clinician"
    assert body["token"]
    row = owner_conn.execute(
        "SELECT kind FROM tenants WHERE id = %s", (body["tenant_id"],)
    ).fetchone()
    assert row == ("demo",)
    records = owner_conn.execute(
        "SELECT count(*) FROM records WHERE tenant_id = %s", (body["tenant_id"],)
    ).fetchone()
    assert records == (75,)


def test_switching_role_keeps_tenant(sign_in: SignIn) -> None:
    first = sign_in("clinician")
    second = sign_in("admin", token=first["token"])
    assert second["tenant_id"] == first["tenant_id"]
    assert second["role"] == "admin"


def test_two_visitors_get_different_tenants(sign_in: SignIn) -> None:
    assert sign_in()["tenant_id"] != sign_in()["tenant_id"]


def test_sign_in_with_token_for_deleted_tenant_gets_new_tenant(
    sign_in: SignIn, owner_conn: psycopg.Connection
) -> None:
    first = sign_in("auditor")
    owner_conn.execute("UPDATE tenants SET expires_at = now() - interval '1 hour'")
    owner_conn.execute("SELECT cleanup_expired_tenants()")
    second = sign_in("auditor", token=first["token"])
    assert second["tenant_id"] != first["tenant_id"]


def test_request_with_token_for_deleted_tenant_returns_401_tenant_expired(
    client: TestClient, sign_in: SignIn, owner_conn: psycopg.Connection
) -> None:
    body = sign_in()
    owner_conn.execute("UPDATE tenants SET expires_at = now() - interval '1 hour'")
    owner_conn.execute("SELECT cleanup_expired_tenants()")
    response = client.get("/api/v1/session", headers=bearer(body["token"]))
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith("/tenant-expired")


def test_missing_token_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/session")
    assert response.status_code == 401


def test_session_echoes_identity(client: TestClient, sign_in: SignIn) -> None:
    body = sign_in("auditor")
    response = client.get("/api/v1/session", headers=bearer(body["token"]))
    assert response.status_code == 200
    assert response.json()["role"] == "auditor"
    assert response.json()["tenant_id"] == body["tenant_id"]


def test_unknown_role_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/auth/demo", json={"role": "superuser"})
    assert response.status_code == 422
