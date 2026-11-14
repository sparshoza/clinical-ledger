"""How document content is encoded to bytes and recognized."""

import json
from typing import Any

JSON_MEDIA_TYPE = "application/json"


def is_json_media(media_type: str) -> bool:
    return media_type == JSON_MEDIA_TYPE or media_type.endswith("+json")


def encode_document(document: Any) -> bytes:
    """Compact, key-sorted JSON bytes. Document content may contain floats (lab values)."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
