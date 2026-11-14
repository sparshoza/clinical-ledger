import pytest

from clinical_ledger.settings import Settings


@pytest.fixture
def required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://ledger_app:x@localhost/db")
    monkeypatch.setenv("S3_BUCKET", "bucket")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("JWT_SECRET", "jwt")
    monkeypatch.setenv("CRON_SECRET", "cron")
    # Defaults are under test, so settings the surrounding shell or CI exports must not leak in.
    for name in ("S3_BACKEND", "S3_REGION", "S3_ENDPOINT_URL", "LEDGER_DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)


def test_defaults(required_env: None) -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.checkpoint_interval == 1000
    assert settings.max_content_bytes == 2_097_152
    assert settings.demo_tenant_ttl_hours == 24
    assert settings.s3_region == "auto"
    assert settings.s3_backend == "s3"


def test_rejects_unknown_backend(required_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S3_BACKEND", "ftp")
    with pytest.raises(ValueError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_ledger_database_url_wins_over_database_url(
    required_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Hosting integrations own DATABASE_URL and point it at the owner login; the app's own
    # restricted connection goes in LEDGER_DATABASE_URL.
    monkeypatch.setenv("LEDGER_DATABASE_URL", "postgresql://ledger_app:y@pooler/db")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.database_url == "postgresql://ledger_app:y@pooler/db"


def test_database_url_still_works_alone(required_env: None) -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.database_url == "postgresql://ledger_app:x@localhost/db"
