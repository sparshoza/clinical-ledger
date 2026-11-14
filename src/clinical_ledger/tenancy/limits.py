"""Limits that keep one visitor from using up the shared free-tier database and storage."""

import hashlib
import hmac
from uuid import UUID

import psycopg
from fastapi import Request

from clinical_ledger.problems import Problem
from clinical_ledger.settings import Settings


def client_address(request: Request) -> str:
    """The visitor's address: the first hop the hosting proxy recorded, else the socket peer."""
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first
    return request.client.host if request.client else "unknown"


def record_signup(conn: psycopg.Connection, settings: Settings, address: str) -> None:
    """Count a new demo ledger against this address, refusing past the hourly limit.

    Only a keyed hash of the address is stored, and the nightly cleanup drops rows after a day.
    """
    client_hash = hmac.new(
        settings.jwt_secret.encode(), address.encode(), hashlib.sha256
    ).hexdigest()
    row = conn.execute(
        "SELECT count(*) FROM demo_signups "
        "WHERE client_hash = %s AND created_at > now() - interval '1 hour'",
        (client_hash,),
    ).fetchone()
    if row is not None and int(row[0]) >= settings.demo_signups_per_hour:
        raise Problem(
            429,
            "too-many-demos",
            "Too many new demo ledgers",
            "This address started several demo ledgers in the last hour. Keep using the one "
            "you have, or try again later.",
        )
    conn.execute("INSERT INTO demo_signups (client_hash) VALUES (%s)", (client_hash,))


def require_write_budget(conn: psycopg.Connection, settings: Settings, tenant_id: UUID) -> None:
    """Refuse new versions once a demo ledger holds its cap. Run in the tenant's transaction."""
    row = conn.execute(
        "SELECT t.kind, count(v.version_no) FROM tenants t "
        "LEFT JOIN versions v ON v.tenant_id = t.id AND v.created_at > t.created_at "
        "WHERE t.id = %s GROUP BY t.kind",
        (tenant_id,),
    ).fetchone()
    if row is not None and row[0] == "demo" and int(row[1]) >= settings.max_new_versions_per_tenant:
        raise Problem(
            429,
            "write-limit",
            "This demo ledger is full",
            f"It already holds {settings.max_new_versions_per_tenant} new versions. Reset the "
            "demo to start a fresh one.",
        )
