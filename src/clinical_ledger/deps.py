"""Request-scoped dependencies: settings, storage, a database connection and the caller."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import Depends, Header, Request

from clinical_ledger.auth.permissions import Permission, allows
from clinical_ledger.auth.tokens import Claims, InvalidToken, decode_token
from clinical_ledger.ledger.models import Actor
from clinical_ledger.problems import Problem
from clinical_ledger.settings import Settings
from clinical_ledger.storage.blobs import BlobStore, make_blob_store
from clinical_ledger.tenancy.seed import Seed, load_seed
from clinical_ledger.tenancy.tenants import tenant_exists


def get_settings(request: Request) -> Settings:
    from clinical_ledger.main import app_settings

    return app_settings(request.app)


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_store(settings: SettingsDep) -> BlobStore:
    return make_blob_store(settings)


def get_seed() -> Seed:
    return load_seed()


def get_conn(settings: SettingsDep) -> Iterator[psycopg.Connection]:
    with psycopg.connect(settings.database_url, connect_timeout=10, autocommit=True) as conn:
        yield conn


ConnDep = Annotated[psycopg.Connection, Depends(get_conn)]
StoreDep = Annotated[BlobStore, Depends(get_store)]
SeedDep = Annotated[Seed, Depends(get_seed)]


@dataclass(frozen=True)
class RequestContext:
    tenant_id: UUID
    actor: Actor
    claims: Claims
    conn: psycopg.Connection
    store: BlobStore
    settings: Settings


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def get_context(
    conn: ConnDep,
    store: StoreDep,
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> RequestContext:
    token = bearer_token(authorization)
    if token is None:
        raise Problem(401, "unauthorized", "Sign in first", "Send a demo token as a Bearer token.")
    try:
        claims = decode_token(token, settings)
    except InvalidToken as exc:
        raise Problem(401, "invalid-token", "The token is not valid", str(exc)) from exc
    if not tenant_exists(conn, claims.tid):
        conn.rollback()
        raise Problem(
            401,
            "tenant-expired",
            "This demo session has expired",
            "Sign in again to get a fresh demo ledger.",
        )
    conn.rollback()
    return RequestContext(
        tenant_id=claims.tid,
        actor=Actor(claims.sub, claims.role),
        claims=claims,
        conn=conn,
        store=store,
        settings=settings,
    )


ContextDep = Annotated[RequestContext, Depends(get_context)]


def require(permission: Permission) -> Callable[[RequestContext], RequestContext]:
    def check(context: ContextDep) -> RequestContext:
        if not allows(context.actor.role, permission):
            raise Problem(
                403,
                "forbidden",
                "Your role cannot do this",
                f"The {context.actor.role} role does not have the {permission.value} permission.",
            )
        return context

    return check
