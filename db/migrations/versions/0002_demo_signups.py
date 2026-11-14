"""Hashed record of demo sign-ups, so each visitor can create a limited number of ledgers.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

CLEANUP_WITH_SIGNUPS = """
CREATE OR REPLACE FUNCTION cleanup_expired_tenants() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    expired uuid[];
BEGIN
    DELETE FROM demo_signups WHERE created_at < now() - interval '1 day';
    SELECT coalesce(array_agg(id), '{}') INTO expired
    FROM tenants WHERE kind = 'demo' AND expires_at < now();
    IF cardinality(expired) = 0 THEN
        RETURN 0;
    END IF;
    PERFORM set_config('ledger.maintenance', 'on', true);
    DELETE FROM blob_overrides WHERE tenant_id = ANY (expired);
    DELETE FROM checkpoints WHERE tenant_id = ANY (expired);
    DELETE FROM events WHERE tenant_id = ANY (expired);
    DELETE FROM record_heads WHERE tenant_id = ANY (expired);
    DELETE FROM versions WHERE tenant_id = ANY (expired);
    DELETE FROM records WHERE tenant_id = ANY (expired);
    DELETE FROM tenants WHERE id = ANY (expired);
    PERFORM set_config('ledger.maintenance', 'off', true);
    RETURN cardinality(expired);
END;
$$;
"""

CLEANUP_BEFORE = """
CREATE OR REPLACE FUNCTION cleanup_expired_tenants() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    expired uuid[];
BEGIN
    SELECT coalesce(array_agg(id), '{}') INTO expired
    FROM tenants WHERE kind = 'demo' AND expires_at < now();
    IF cardinality(expired) = 0 THEN
        RETURN 0;
    END IF;
    PERFORM set_config('ledger.maintenance', 'on', true);
    DELETE FROM blob_overrides WHERE tenant_id = ANY (expired);
    DELETE FROM checkpoints WHERE tenant_id = ANY (expired);
    DELETE FROM events WHERE tenant_id = ANY (expired);
    DELETE FROM record_heads WHERE tenant_id = ANY (expired);
    DELETE FROM versions WHERE tenant_id = ANY (expired);
    DELETE FROM records WHERE tenant_id = ANY (expired);
    DELETE FROM tenants WHERE id = ANY (expired);
    PERFORM set_config('ledger.maintenance', 'off', true);
    RETURN cardinality(expired);
END;
$$;
"""


def upgrade() -> None:
    # Only a salted hash of the visitor's address is kept, and only for a day.
    op.execute(
        "CREATE TABLE demo_signups ("
        "client_hash text NOT NULL, created_at timestamptz NOT NULL DEFAULT now())"
    )
    op.execute("CREATE INDEX demo_signups_client_idx ON demo_signups (client_hash, created_at)")
    op.execute("GRANT SELECT, INSERT ON demo_signups TO ledger_app")
    op.execute(CLEANUP_WITH_SIGNUPS)


def downgrade() -> None:
    op.execute(CLEANUP_BEFORE)
    op.execute("DROP TABLE demo_signups")
