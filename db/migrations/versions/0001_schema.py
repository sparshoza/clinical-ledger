"""Ledger schema: tables, row-level security, append-only guards and the app role.

Revision ID: 0001
"""

import os

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "records",
    "versions",
    "record_heads",
    "events",
    "checkpoints",
    "blob_overrides",
)
APPEND_ONLY_TABLES = ("blobs", "versions", "events", "checkpoints")

# Maintenance mode is honored only for roles other than ledger_app. Any role can set a
# custom setting, so the role check is what stops the app from unlocking itself.
MAINTENANCE = (
    "(current_setting('ledger.maintenance', true) = 'on' AND current_user <> 'ledger_app')"
)

SCHEMA = """
CREATE TABLE tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('demo', 'standard')),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz
);
CREATE INDEX tenants_expiry_idx ON tenants (expires_at) WHERE kind = 'demo';

CREATE TABLE actors (
    id uuid PRIMARY KEY,
    display_name text NOT NULL,
    role text NOT NULL CHECK (role IN ('clinician', 'auditor', 'admin'))
);

CREATE TABLE blobs (
    content_hash text PRIMARY KEY CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    media_type text NOT NULL,
    storage_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE records (
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    id uuid NOT NULL,
    kind text NOT NULL,
    subject_ref text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid NOT NULL REFERENCES actors (id),
    PRIMARY KEY (tenant_id, id)
);

CREATE TABLE versions (
    tenant_id uuid NOT NULL,
    record_id uuid NOT NULL,
    version_no integer NOT NULL CHECK (version_no > 0),
    content_hash text NOT NULL REFERENCES blobs (content_hash),
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid NOT NULL REFERENCES actors (id),
    note text NOT NULL DEFAULT '',
    PRIMARY KEY (tenant_id, record_id, version_no),
    FOREIGN KEY (tenant_id, record_id) REFERENCES records (tenant_id, id)
);
CREATE INDEX versions_as_of_idx ON versions (tenant_id, record_id, created_at);

CREATE TABLE record_heads (
    tenant_id uuid NOT NULL,
    record_id uuid NOT NULL,
    latest_version_no integer NOT NULL,
    latest_content_hash text NOT NULL REFERENCES blobs (content_hash),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, record_id),
    FOREIGN KEY (tenant_id, record_id) REFERENCES records (tenant_id, id)
);

CREATE TABLE events (
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    seq bigint NOT NULL CHECK (seq > 0),
    event_type text NOT NULL,
    record_id uuid,
    version_no integer,
    actor uuid NOT NULL REFERENCES actors (id),
    actor_role text NOT NULL,
    occurred_at timestamptz NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    prev_hash text NOT NULL,
    event_hash text NOT NULL,
    PRIMARY KEY (tenant_id, seq)
);
CREATE INDEX events_record_idx ON events (tenant_id, record_id, seq);

CREATE TABLE checkpoints (
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    seq bigint NOT NULL,
    event_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, seq)
);

CREATE TABLE blob_overrides (
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    content_hash text NOT NULL REFERENCES blobs (content_hash),
    storage_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, content_hash)
);
"""

FORBID_MUTATION = f"""
CREATE FUNCTION forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF {MAINTENANCE} THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    RAISE EXCEPTION 'append-only table: %', TG_TABLE_NAME;
END;
$$;
"""

DEMO_TAMPER_EVENT = """
CREATE FUNCTION demo_tamper_event(p_tenant uuid, p_seq bigint) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    IF p_tenant::text IS DISTINCT FROM current_setting('app.tenant_id', true) THEN
        RAISE EXCEPTION 'demo_tamper_event may only change the caller''s own tenant';
    END IF;
    PERFORM set_config('ledger.maintenance', 'on', true);
    UPDATE events SET payload = payload || '{"tampered": true}'::jsonb
    WHERE tenant_id = p_tenant AND seq = p_seq;
    PERFORM set_config('ledger.maintenance', 'off', true);
END;
$$;
"""

CLEANUP_EXPIRED_TENANTS = """
CREATE FUNCTION cleanup_expired_tenants() RETURNS integer
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


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    password = os.environ.get("LEDGER_APP_PASSWORD")
    if not password:
        raise RuntimeError("Set LEDGER_APP_PASSWORD so the migration can create ledger_app")

    op.execute(SCHEMA)
    op.execute(FORBID_MUTATION)
    for table in APPEND_ONLY_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION forbid_mutation()"
        )
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            "USING (tenant_id::text = current_setting('app.tenant_id', true) "
            f"OR {MAINTENANCE}) "
            "WITH CHECK (tenant_id::text = current_setting('app.tenant_id', true))"
        )
    op.execute(DEMO_TAMPER_EVENT)
    op.execute(CLEANUP_EXPIRED_TENANTS)

    literal = _quote_literal(password)
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ledger_app') THEN "
        f"CREATE ROLE ledger_app LOGIN PASSWORD {literal}; "
        f"ELSE ALTER ROLE ledger_app LOGIN PASSWORD {literal}; "
        "END IF; END $$"
    )
    op.execute(
        "DO $$ BEGIN EXECUTE format('GRANT CONNECT ON DATABASE %I TO ledger_app', "
        "current_database()); END $$"
    )
    op.execute("GRANT USAGE ON SCHEMA public TO ledger_app")
    op.execute(
        "GRANT SELECT, INSERT ON tenants, actors, blobs, records, versions, record_heads, "
        "events, checkpoints, blob_overrides TO ledger_app"
    )
    op.execute("GRANT UPDATE ON record_heads TO ledger_app")
    op.execute("REVOKE ALL ON FUNCTION demo_tamper_event(uuid, bigint) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION cleanup_expired_tenants() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION demo_tamper_event(uuid, bigint) TO ledger_app")
    op.execute("GRANT EXECUTE ON FUNCTION cleanup_expired_tenants() TO ledger_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS cleanup_expired_tenants()")
    op.execute("DROP FUNCTION IF EXISTS demo_tamper_event(uuid, bigint)")
    for table in reversed(("tenants", "actors", "blobs", *TENANT_TABLES)):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS forbid_mutation()")
