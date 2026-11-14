"""Content-addressed object storage over any S3-compatible service."""

import threading
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from clinical_ledger.settings import Settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import ObjectIdentifierTypeDef


class BlobNotFound(Exception):
    """Raised when no object exists at a key."""


class BlobStore(Protocol):
    def put(self, key: str, data: bytes, media_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def delete_prefix(self, prefix: str) -> None: ...


def blob_key(content_hash: str) -> str:
    return f"blobs/{content_hash}"


def override_key(tenant_id: UUID, content_hash: str) -> str:
    return f"overrides/{tenant_id}/{content_hash}"


class InMemoryBlobStore:
    """Process-local store for tests and local end-to-end runs."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, media_type: str) -> None:
        self._objects[key] = data

    def get(self, key: str) -> bytes:
        try:
            return self._objects[key]
        except KeyError:
            raise BlobNotFound(key) from None

    def exists(self, key: str) -> bool:
        return key in self._objects

    def delete_prefix(self, prefix: str) -> None:
        for key in [k for k in self._objects if k.startswith(prefix)]:
            del self._objects[key]


_NOT_FOUND_CODES = {"NoSuchKey", "404", "NotFound"}


class S3BlobStore:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._client: S3Client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
            # Fail fast inside a serverless time limit, and allow one connection per verify
            # worker so parallel fetches never queue for the pool.
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=3,
                read_timeout=10,
                max_pool_connections=32,
            ),
        )

    def put(self, key: str, data: bytes, media_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=media_type)

    def get(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
                raise BlobNotFound(key) from exc
            raise
        return response["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
                return False
            raise
        return True

    def delete_prefix(self, prefix: str) -> None:
        """Delete every object under `prefix` (used only for a demo tenant's tampered copies)."""
        pages = self._client.get_paginator("list_objects_v2").paginate(
            Bucket=self._bucket, Prefix=prefix
        )
        for page in pages:
            keys: list[ObjectIdentifierTypeDef] = [
                {"Key": item["Key"]} for item in page.get("Contents", [])
            ]
            if keys:
                self._client.delete_objects(Bucket=self._bucket, Delete={"Objects": keys})


_memory_store: InMemoryBlobStore | None = None
_s3_stores: dict[tuple[str | None, str, str], S3BlobStore] = {}
_s3_lock = threading.Lock()


def make_blob_store(settings: Settings) -> BlobStore:
    """Return the configured store, built once per process and shared across requests.

    Building a boto3 client is slow and not thread-safe on first use, so the S3 store is
    created under a lock and reused; its client is safe to share between threads.
    """
    global _memory_store
    if settings.s3_backend == "memory":
        if _memory_store is None:
            _memory_store = InMemoryBlobStore()
        return _memory_store
    key = (settings.s3_endpoint_url, settings.s3_bucket, settings.s3_access_key_id)
    with _s3_lock:
        if key not in _s3_stores:
            _s3_stores[key] = S3BlobStore(settings)
        return _s3_stores[key]
