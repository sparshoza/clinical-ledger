"""Content-addressed object storage over any S3-compatible service."""

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from clinical_ledger.settings import Settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


class BlobNotFound(Exception):
    """Raised when no object exists at a key."""


class BlobStore(Protocol):
    def put(self, key: str, data: bytes, media_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...


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
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
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


_memory_store: InMemoryBlobStore | None = None


def make_blob_store(settings: Settings) -> BlobStore:
    """Return the configured store. The memory store is shared within a process."""
    global _memory_store
    if settings.s3_backend == "memory":
        if _memory_store is None:
            _memory_store = InMemoryBlobStore()
        return _memory_store
    return S3BlobStore(settings)
