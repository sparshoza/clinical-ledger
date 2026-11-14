"""Signed demo tokens (JWT, HS256) carrying the actor, role and tenant."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

import jwt

from clinical_ledger.settings import Settings

Role = Literal["clinician", "auditor", "admin"]
ROLES: tuple[Role, ...] = ("clinician", "auditor", "admin")
ALGORITHM = "HS256"
LEEWAY_SECONDS = 10


class InvalidToken(Exception):
    """The token is missing, malformed, expired or not signed by us."""


@dataclass(frozen=True)
class Claims:
    sub: UUID
    role: Role
    tid: UUID
    exp: datetime


def issue_token(
    actor_id: UUID,
    role: Role,
    tenant_id: UUID,
    settings: Settings,
    expires_at: datetime | None = None,
) -> str:
    expiry = expires_at or datetime.now(UTC) + timedelta(hours=settings.demo_tenant_ttl_hours)
    payload = {"sub": str(actor_id), "role": role, "tid": str(tenant_id), "exp": expiry}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str, settings: Settings) -> Claims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            leeway=LEEWAY_SECONDS,
            options={"require": ["sub", "role", "tid", "exp"]},
        )
        role = payload["role"]
        if role not in ROLES:
            raise InvalidToken("unknown role")
        return Claims(
            sub=UUID(payload["sub"]),
            role=cast(Role, role),
            tid=UUID(payload["tid"]),
            exp=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise InvalidToken(str(exc)) from exc
