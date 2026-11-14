"""Database helpers. Every request runs in one transaction scoped to one tenant."""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import psycopg


@contextmanager
def tenant_transaction(conn: psycopg.Connection, tenant_id: UUID) -> Iterator[psycopg.Connection]:
    """Open a transaction in which row-level security sees only `tenant_id`'s rows."""
    with conn.transaction():
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
        yield conn
