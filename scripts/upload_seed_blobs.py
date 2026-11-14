"""Install the shared seed rows (demo actors and seed blobs) into a database and bucket.

Run once per environment after migrations, with the owner connection:
    python scripts/upload_seed_blobs.py

Reads DATABASE_URL_OWNER and the S3_* settings from the environment (or .env).
Safe to re-run: existing actors, blob rows and objects are left as they are.
"""

import os

import psycopg
from dotenv import load_dotenv

from clinical_ledger.settings import Settings
from clinical_ledger.storage.blobs import make_blob_store
from clinical_ledger.tenancy.seed import install_seed, load_seed


def main() -> None:
    load_dotenv()
    owner_url = os.environ.get("DATABASE_URL_OWNER")
    if not owner_url:
        raise SystemExit("Set DATABASE_URL_OWNER")
    settings = Settings()  # type: ignore[call-arg]
    seed = load_seed()
    with psycopg.connect(owner_url, autocommit=True) as conn:
        install_seed(conn, make_blob_store(settings), seed)
    print(f"installed {len(seed.actors)} actors and {len(seed.blobs)} blobs")


if __name__ == "__main__":
    main()
