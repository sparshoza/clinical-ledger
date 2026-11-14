"""Alembic environment. Migrations run with the owner connection, never as ledger_app.

The URL comes from `config.attributes["database_url"]` (set by tests and scripts) or the
DATABASE_URL_OWNER environment variable.
"""

import os

from alembic import context
from sqlalchemy import create_engine, pool

config = context.config


def _database_url() -> str:
    url = config.attributes.get("database_url") or os.environ.get("DATABASE_URL_OWNER")
    if not url:
        try:
            from dotenv import load_dotenv

            load_dotenv()
            url = os.environ.get("DATABASE_URL_OWNER")
        except ImportError:
            url = None
    if not url:
        raise RuntimeError("Set DATABASE_URL_OWNER to run migrations")
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return str(url)


def run_migrations() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
