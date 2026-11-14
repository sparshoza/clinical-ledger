"""API test client wired to the test database (as ledger_app) and in-memory storage."""

from collections.abc import Callable, Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient

from clinical_ledger.main import create_app
from clinical_ledger.settings import Settings
from clinical_ledger.storage.blobs import make_blob_store
from clinical_ledger.tenancy.seed import install_seed, load_seed
from tests.conftest import make_settings


@pytest.fixture
def api_settings(app_dsn: str) -> Settings:
    return make_settings(database_url=app_dsn)


@pytest.fixture
def client(
    api_settings: Settings, owner_conn: psycopg.Connection, clean_tables: None
) -> Iterator[TestClient]:
    install_seed(owner_conn, make_blob_store(api_settings), load_seed())
    with TestClient(create_app(api_settings)) as test_client:
        yield test_client


@pytest.fixture
def sign_in(client: TestClient) -> Callable[..., dict[str, str]]:
    """Sign in as a role; returns the JSON body. Pass `token` to switch role."""

    def _sign_in(role: str = "clinician", token: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = client.post("/api/v1/auth/demo", json={"role": role}, headers=headers)
        assert response.status_code == 200, response.text
        body: dict[str, str] = response.json()
        return body

    return _sign_in


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
