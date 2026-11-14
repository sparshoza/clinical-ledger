from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import bearer

pytestmark = pytest.mark.integration

SignIn = Callable[..., dict[str, str]]


def test_auditor_can_list_events(client: TestClient, sign_in: SignIn) -> None:
    headers = bearer(sign_in("auditor")["token"])
    response = client.get("/api/v1/events", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 50
    seqs = [event["seq"] for event in body["items"]]
    assert seqs == sorted(seqs, reverse=True)
    assert body["next_before_seq"] == seqs[-1]
    assert {
        "seq",
        "event_type",
        "actor",
        "actor_role",
        "occurred_at",
        "event_hash",
        "prev_hash",
        "payload",
    } <= set(body["items"][0])


def test_events_page_backwards(client: TestClient, sign_in: SignIn) -> None:
    headers = bearer(sign_in("auditor")["token"])
    first = client.get("/api/v1/events?limit=10", headers=headers).json()
    second = client.get(
        f"/api/v1/events?limit=10&before_seq={first['next_before_seq']}", headers=headers
    ).json()
    assert second["items"][0]["seq"] == first["items"][-1]["seq"] - 1


def test_reads_appear_in_the_log(client: TestClient, sign_in: SignIn) -> None:
    session = sign_in("clinician")
    headers = bearer(session["token"])
    record = client.get("/api/v1/records?limit=1", headers=headers).json()["items"][0]["id"]
    client.get(f"/api/v1/records/{record}", headers=headers)
    events = client.get(
        f"/api/v1/events?record_id={record}&event_type=record.read", headers=headers
    ).json()["items"]
    assert len(events) == 1
    assert events[0]["actor_role"] == "clinician"
