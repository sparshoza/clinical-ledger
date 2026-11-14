from collections.abc import Iterator
from uuid import UUID

import boto3
import pytest
from moto import mock_aws

from clinical_ledger.settings import Settings
from clinical_ledger.storage.blobs import (
    BlobNotFound,
    BlobStore,
    InMemoryBlobStore,
    S3BlobStore,
    blob_key,
    make_blob_store,
    override_key,
)
from tests.conftest import make_settings


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql://x@localhost/x",
        "s3_bucket": "clinical-ledger",
        "s3_access_key_id": "test",
        "s3_secret_access_key": "test",
        "s3_region": "us-east-1",
        "s3_endpoint_url": None,  # never reach a real service from tests
        "s3_backend": "s3",
        "jwt_secret": "x",
        "cron_secret": "x",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg, arg-type]


@pytest.fixture(params=["memory", "s3"])
def store(request: pytest.FixtureRequest) -> Iterator[BlobStore]:
    if request.param == "memory":
        yield InMemoryBlobStore()
        return
    with mock_aws():
        settings = _settings()
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=settings.s3_bucket)
        yield S3BlobStore(settings)


def test_put_get_roundtrip(store: BlobStore) -> None:
    store.put("blobs/abc", b'{"a":1}', "application/json")
    assert store.get("blobs/abc") == b'{"a":1}'


def test_get_missing_raises_blob_not_found(store: BlobStore) -> None:
    with pytest.raises(BlobNotFound):
        store.get("blobs/missing")


def test_exists(store: BlobStore) -> None:
    assert not store.exists("blobs/abc")
    store.put("blobs/abc", b"x", "text/plain")
    assert store.exists("blobs/abc")


def test_keys() -> None:
    tenant = UUID("00000000-0000-0000-0000-000000000001")
    assert blob_key("f" * 64) == "blobs/" + "f" * 64
    assert override_key(tenant, "f" * 64) == f"overrides/{tenant}/" + "f" * 64


def test_make_blob_store_picks_backend() -> None:
    assert isinstance(make_blob_store(_settings(s3_backend="memory")), InMemoryBlobStore)
    assert isinstance(make_blob_store(_settings(s3_backend="s3")), S3BlobStore)


def test_s3_store_is_built_once_per_process_with_timeouts_and_pool() -> None:
    from clinical_ledger.ledger.verify import BLOB_WORKERS
    from clinical_ledger.storage.blobs import S3BlobStore, make_blob_store

    settings = make_settings(s3_backend="s3", s3_endpoint_url="https://example.invalid")
    store = make_blob_store(settings)
    assert isinstance(store, S3BlobStore)
    assert make_blob_store(settings) is store
    config = store._client.meta.config
    assert config.max_pool_connections >= BLOB_WORKERS
    assert config.connect_timeout <= 5
    assert config.read_timeout <= 15
