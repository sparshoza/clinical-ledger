import uuid
from datetime import UTC, datetime, timedelta

import pytest

from clinical_ledger.auth.tokens import InvalidToken, decode_token, issue_token
from tests.conftest import make_settings


def test_token_roundtrip() -> None:
    settings = make_settings()
    actor, tenant = uuid.uuid4(), uuid.uuid4()
    claims = decode_token(issue_token(actor, "auditor", tenant, settings), settings)
    assert claims.sub == actor
    assert claims.role == "auditor"
    assert claims.tid == tenant
    assert claims.exp > datetime.now(UTC) + timedelta(hours=23)


def test_expired_token_rejected() -> None:
    settings = make_settings()
    past = datetime.now(UTC) - timedelta(minutes=5)
    token = issue_token(uuid.uuid4(), "admin", uuid.uuid4(), settings, expires_at=past)
    with pytest.raises(InvalidToken):
        decode_token(token, settings)


def test_tampered_token_rejected() -> None:
    settings = make_settings()
    header, payload, signature = issue_token(
        uuid.uuid4(), "clinician", uuid.uuid4(), settings
    ).split(".")
    forged = ".".join([header, payload[:-2] + ("AA" if payload[-2:] != "AA" else "BB"), signature])
    with pytest.raises(InvalidToken):
        decode_token(forged, settings)


def test_token_signed_with_other_secret_rejected() -> None:
    token = issue_token(uuid.uuid4(), "clinician", uuid.uuid4(), make_settings())
    with pytest.raises(InvalidToken):
        decode_token(token, make_settings(jwt_secret="another-secret-that-is-32-bytes-long"))
