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
