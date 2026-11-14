from collections.abc import Callable

import psycopg
import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import bearer

pytestmark = pytest.mark.integration

SignIn = Callable[..., dict[str, str]]


@pytest.fixture
def admin(sign_in: SignIn) -> dict[str, str]:
    return bearer(sign_in("admin")["token"])


def _verify(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    response = client.post("/api/v1/verify", json={}, headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


def test_verify_ok_on_fresh_tenant(client: TestClient, admin: dict[str, str]) -> None:
    result = _verify(client, admin)
    assert result["ok"] is True
    assert result["checked_events"] == 350
    assert result["first_broken_seq"] is None


def test_auditor_can_verify_but_clinician_cannot(client: TestClient, sign_in: SignIn) -> None:
    assert _verify(client, bearer(sign_in("auditor")["token"]))["ok"] is True
    response = client.post("/api/v1/verify", json={}, headers=bearer(sign_in("clinician")["token"]))
    assert response.status_code == 403


def test_tamper_event_then_verify_reports_target_seq(
    client: TestClient, admin: dict[str, str]
) -> None:
    tamper = client.post("/api/v1/demo/tamper", json={"mode": "event"}, headers=admin)
    assert tamper.status_code == 200
    target = tamper.json()["target_seq"]
    assert target == 175
    result = _verify(client, admin)
    assert result["ok"] is False
    assert result["first_broken_seq"] == target
    assert result["reason"] == "hash_mismatch"
    assert result["stored_hash"] != result["computed_hash"]
    assert len(result["computed_hash"]) == 64


def test_tamper_blob_then_read_returns_409_and_verify_reports_blob_mismatch(
    client: TestClient, admin: dict[str, str]
) -> None:
    tamper = client.post("/api/v1/demo/tamper", json={"mode": "blob"}, headers=admin)
    assert tamper.status_code == 200
    record = tamper.json()["target_record_id"]
    read = client.get(f"/api/v1/records/{record}", headers=admin)
    assert read.status_code == 409
    assert read.json()["type"].endswith("/content-tampered")
    result = _verify(client, admin)
    assert result["ok"] is False
    assert result["reason"] == "blob_mismatch"


def test_tamper_twice_is_harmless(client: TestClient, admin: dict[str, str]) -> None:
    for mode in ("blob", "blob", "event", "event"):
        assert client.post("/api/v1/demo/tamper", json={"mode": mode}, headers=admin).is_success


def test_tamper_requires_admin(client: TestClient, sign_in: SignIn) -> None:
    for role in ("clinician", "auditor"):
        response = client.post(
            "/api/v1/demo/tamper", json={"mode": "event"}, headers=bearer(sign_in(role)["token"])
        )
        assert response.status_code == 403


def test_tamper_does_not_affect_other_visitors(
    client: TestClient, admin: dict[str, str], sign_in: SignIn
) -> None:
    other = bearer(sign_in("admin")["token"])
    client.post("/api/v1/demo/tamper", json={"mode": "event"}, headers=admin)
    client.post("/api/v1/demo/tamper", json={"mode": "blob"}, headers=admin)
    assert _verify(client, other)["ok"] is True


def test_reset_gives_clean_tenant(client: TestClient, sign_in: SignIn) -> None:
    session = sign_in("admin")
    headers = bearer(session["token"])
    client.post("/api/v1/demo/tamper", json={"mode": "event"}, headers=headers)
    reset = client.post("/api/v1/demo/reset", headers=headers)
    assert reset.status_code == 200
    body = reset.json()
    assert body["tenant_id"] != session["tenant_id"]
    assert body["role"] == "admin"
    assert _verify(client, bearer(body["token"]))["ok"] is True


def test_stats_counts_match(client: TestClient, admin: dict[str, str]) -> None:
    stats = client.get("/api/v1/stats", headers=admin).json()
    assert stats["records"] == 75
    assert stats["versions"] == 350
    assert stats["events"] == 350
    assert stats["head_seq"] == 350
    assert len(stats["head_hash"]) == 64
    assert stats["last_verify"] is None
    assert stats["tenant_expires_at"]
    _verify(client, admin)
    after = client.get("/api/v1/stats", headers=admin).json()
    assert after["last_verify"]["ok"] is True
    assert after["events"] == 351


def test_cron_requires_secret(client: TestClient) -> None:
    assert client.get("/api/v1/cron/cleanup").status_code == 401
    wrong = client.get("/api/v1/cron/cleanup", headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 401


def test_cron_removes_expired(
    client: TestClient, sign_in: SignIn, owner_conn: psycopg.Connection
) -> None:
    sign_in()
    live = sign_in()
    owner_conn.execute(
        "UPDATE tenants SET expires_at = now() - interval '1 minute' WHERE id <> %s",
        (live["tenant_id"],),
    )
    response = client.get(
        "/api/v1/cron/cleanup", headers={"Authorization": "Bearer test-cron-secret"}
    )
    assert response.status_code == 200
    assert response.json() == {"removed": 1}
    remaining = owner_conn.execute("SELECT count(*) FROM tenants").fetchone()
    assert remaining == (1,)
