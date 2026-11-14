"""Demo sign-in and the current session."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Header
from pydantic import BaseModel

from clinical_ledger.auth.tokens import InvalidToken, Role, decode_token, issue_token
from clinical_ledger.deps import ConnDep, ContextDep, SeedDep, SettingsDep, bearer_token
from clinical_ledger.settings import Settings
from clinical_ledger.tenancy.seed import Seed
from clinical_ledger.tenancy.tenants import create_demo_tenant

router = APIRouter(tags=["auth"])


class DemoSignIn(BaseModel):
    role: Role


class SessionOut(BaseModel):
    token: str
    tenant_id: UUID
    role: Role
    expires_at: datetime


class WhoAmI(BaseModel):
    tenant_id: UUID
    actor_id: UUID
    role: Role
    expires_at: datetime


@router.post("/auth/demo", response_model=SessionOut, summary="Start or switch a demo session")
def demo_sign_in(
    body: DemoSignIn,
    conn: ConnDep,
    settings: SettingsDep,
    seed: SeedDep,
    authorization: Annotated[str | None, Header()] = None,
) -> SessionOut:
    """Sign in as a demo role. A valid token for a live tenant keeps that tenant."""
    tenant_id: UUID | None = None
    expires_at: datetime | None = None
    token = bearer_token(authorization)
    if token is not None:
        try:
            claims = decode_token(token, settings)
        except InvalidToken:
            claims = None
        if claims is not None:
            row = conn.execute(
                "SELECT expires_at FROM tenants WHERE id = %s", (claims.tid,)
            ).fetchone()
            if row is not None:
                tenant_id, expires_at = claims.tid, row[0]
    return start_session(conn, settings, seed, body.role, tenant_id, expires_at)


def start_session(
    conn: psycopg.Connection,
    settings: Settings,
    seed: Seed,
    role: Role,
    tenant_id: UUID | None = None,
    expires_at: datetime | None = None,
) -> SessionOut:
    """Issue a token for `role`, creating a fresh demo tenant when none is given."""
    if tenant_id is None:
        tenant_id = create_demo_tenant(conn, settings, seed)
        row = conn.execute("SELECT expires_at FROM tenants WHERE id = %s", (tenant_id,)).fetchone()
        expires_at = row[0] if row else None
    conn.commit()
    actor = seed.actor_for(role)
    new_token = issue_token(actor.id, role, tenant_id, settings, expires_at=expires_at)
    claims_out = decode_token(new_token, settings)
    return SessionOut(token=new_token, tenant_id=tenant_id, role=role, expires_at=claims_out.exp)


@router.get("/session", response_model=WhoAmI, summary="Who the current token belongs to")
def session(context: ContextDep) -> WhoAmI:
    return WhoAmI(
        tenant_id=context.tenant_id,
        actor_id=context.actor.id,
        role=context.claims.role,
        expires_at=context.claims.exp,
    )
