import base64
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import bearer

pytestmark = pytest.mark.integration

SignIn = Callable[..., dict[str, str]]


@pytest.fixture
def clinician(sign_in: SignIn) -> dict[str, str]:
    return bearer(sign_in("clinician")["token"])


def _create(client: TestClient, headers: dict[str, str], **body: Any) -> dict[str, Any]:
    payload = {"kind": "lab-panel", "subject_ref": "Patient/demo", **body}
    response = client.post("/api/v1/records", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def test_list_records_returns_seeded_records(client: TestClient, clinician: dict[str, str]) -> None:
    response = client.get("/api/v1/records?limit=10", headers=clinician)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 10
    assert body["next_cursor"] == body["items"][-1]["id"]
    assert {"id", "kind", "subject_ref", "latest_version_no", "updated_at"} <= set(body["items"][0])


def test_pagination_cursor(client: TestClient, clinician: dict[str, str]) -> None:
    first = client.get("/api/v1/records?limit=50", headers=clinician).json()
    second = client.get(
        f"/api/v1/records?limit=50&cursor={first['next_cursor']}", headers=clinician
    ).json()
    assert len(first["items"]) + len(second["items"]) == 75
    assert second["next_cursor"] is None
    assert not {i["id"] for i in first["items"]} & {i["id"] for i in second["items"]}


def test_limit_capped_at_100(client: TestClient, clinician: dict[str, str]) -> None:
    response = client.get("/api/v1/events?limit=500", headers=clinician)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 100


def test_create_and_read_json_record(client: TestClient, clinician: dict[str, str]) -> None:
    created = _create(client, clinician, content_json={"status": "preliminary"})
    assert created["version_no"] == 1
    response = client.get(f"/api/v1/records/{created['record_id']}", headers=clinician)
    assert response.status_code == 200
    body = response.json()
    assert body["content_json"] == {"status": "preliminary"}
    assert body["media_type"] == "application/json"
    assert body["version"]["version_no"] == 1


def test_create_binary_record_round_trips_base64(
    client: TestClient, clinician: dict[str, str]
) -> None:
    data = b"%PDF-1.7 synthetic"
    created = _create(
        client, clinician, content_b64=base64.b64encode(data).decode(), media_type="application/pdf"
    )
    body = client.get(f"/api/v1/records/{created['record_id']}", headers=clinician).json()
    assert base64.b64decode(body["content_b64"]) == data
    assert "content_json" not in body or body["content_json"] is None


def test_create_requires_exactly_one_content_field(
    client: TestClient, clinician: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/records",
        json={"kind": "x", "subject_ref": "y", "content_json": {}, "content_b64": "AA=="},
        headers=clinician,
    )
    assert response.status_code == 422


def test_add_version_and_list_versions(client: TestClient, clinician: dict[str, str]) -> None:
    created = _create(client, clinician, content_json={"v": 1})
    record = created["record_id"]
    response = client.post(
        f"/api/v1/records/{record}/versions",
        json={"content_json": {"v": 2}, "note": "second"},
        headers=clinician,
    )
    assert response.status_code == 201
    assert response.json()["version_no"] == 2
    versions = client.get(f"/api/v1/records/{record}/versions", headers=clinician).json()
    assert [v["version_no"] for v in versions["items"]] == [1, 2]
    assert versions["items"][1]["note"] == "second"
    one = client.get(f"/api/v1/records/{record}/versions/1", headers=clinician).json()
    assert one["content_json"] == {"v": 1}


def test_as_of_query(client: TestClient, clinician: dict[str, str]) -> None:
    created = _create(client, clinician, content_json={"v": 1})
    record = created["record_id"]
    client.post(
        f"/api/v1/records/{record}/versions", json={"content_json": {"v": 2}}, headers=clinician
    )
    response = client.get(
        f"/api/v1/records/{record}", params={"as_of": created["created_at"]}, headers=clinician
    )
    assert response.json()["version"]["version_no"] == 1


def test_diff(client: TestClient, clinician: dict[str, str]) -> None:
    created = _create(client, clinician, content_json={"status": "preliminary"})
    record = created["record_id"]
    client.post(
        f"/api/v1/records/{record}/versions",
        json={"content_json": {"status": "final"}},
        headers=clinician,
    )
    response = client.get(f"/api/v1/records/{record}/diff?from=1&to=2", headers=clinician)
    assert response.json()["ops"] == [{"op": "replace", "path": "/status", "value": "final"}]


def test_unknown_record_is_404_problem(client: TestClient, clinician: dict[str, str]) -> None:
    response = client.get(f"/api/v1/records/{uuid.uuid4()}", headers=clinician)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert set(response.json()) >= {"type", "title", "status", "detail"}


def test_content_too_large_is_413(client: TestClient, clinician: dict[str, str]) -> None:
    big = base64.b64encode(b"x" * 2_097_153).decode()
    response = client.post(
        "/api/v1/records",
        json={
            "kind": "file",
            "subject_ref": "p",
            "content_b64": big,
            "media_type": "application/octet-stream",
        },
        headers=clinician,
    )
    assert response.status_code == 413


def test_auditor_cannot_read_content(client: TestClient, sign_in: SignIn) -> None:
    session = sign_in("auditor")
    headers = bearer(session["token"])
    record = client.get("/api/v1/records?limit=1", headers=headers).json()["items"][0]["id"]
    response = client.get(f"/api/v1/records/{record}", headers=headers)
    assert response.status_code == 403
    assert response.json()["type"].endswith("/forbidden")


def test_auditor_cannot_write(client: TestClient, sign_in: SignIn) -> None:
    headers = bearer(sign_in("auditor")["token"])
    response = client.post(
        "/api/v1/records",
        json={"kind": "x", "subject_ref": "y", "content_json": {}},
        headers=headers,
    )
    assert response.status_code == 403


def test_tenants_are_isolated_over_http(client: TestClient, sign_in: SignIn) -> None:
    alice = bearer(sign_in("clinician")["token"])
    bob = bearer(sign_in("clinician")["token"])
    created = _create(client, alice, content_json={"private": True})
    response = client.get(f"/api/v1/records/{created['record_id']}", headers=bob)
    assert response.status_code == 404


def test_demo_edit_adds_version_with_description_note(
    client: TestClient, clinician: dict[str, str]
) -> None:
    record = next(
        item
        for item in client.get("/api/v1/records?limit=100", headers=clinician).json()["items"]
        if item["kind"] == "lab-panel"
    )
    before = client.get(f"/api/v1/records/{record['id']}", headers=clinician).json()
    response = client.post(f"/api/v1/records/{record['id']}/demo-edit", headers=clinician)
    assert response.status_code == 201, response.text
    version = response.json()
    assert version["version_no"] == record["latest_version_no"] + 1
    assert version["note"].startswith("Added lab result")
    after = client.get(f"/api/v1/records/{record['id']}", headers=clinician).json()
    assert len(after["content_json"]["observations"]) == (
        len(before["content_json"]["observations"]) + 1
    )


def test_demo_edit_requires_write(client: TestClient, sign_in: SignIn) -> None:
    headers = bearer(sign_in("auditor")["token"])
    record = client.get("/api/v1/records?limit=1", headers=headers).json()["items"][0]["id"]
    assert client.post(f"/api/v1/records/{record}/demo-edit", headers=headers).status_code == 403
