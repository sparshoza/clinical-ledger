import psycopg
import pytest
from fastapi.testclient import TestClient

from clinical_ledger.deps import get_context
from clinical_ledger.main import create_app
from clinical_ledger.settings import Settings

pytestmark = pytest.mark.integration


def _unavailable() -> None:
    raise psycopg.OperationalError("connection refused")


def test_database_unavailable_returns_503(api_settings: Settings) -> None:
    app = create_app(api_settings)
    app.dependency_overrides[get_context] = _unavailable
    with TestClient(app) as client:
        response = client.get("/api/v1/records")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith("/unavailable")


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "storage": "ok"}


def test_health_reports_database_down(api_settings: Settings) -> None:
    broken = api_settings.model_copy(
        update={"database_url": "postgresql://nobody:x@127.0.0.1:1/none"}
    )
    with TestClient(create_app(broken)) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"


def test_request_id_header_present(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert len(response.headers["x-request-id"]) >= 16
    echoed = client.get("/api/v1/health", headers={"X-Request-ID": "abc123"})
    assert echoed.headers["x-request-id"] == "abc123"


def test_unknown_route_is_problem_json(client: TestClient) -> None:
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
