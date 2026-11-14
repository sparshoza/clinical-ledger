"""Time demo tenant creation, the work behind a visitor's first click.

Usage: python -m bench.tenant_create [--database-url URL] [--label neon] [--count 20]
The URL must be the application login (ledger_app) of a migrated database whose seed
blobs are installed. Each creation opens its own connection, as a serverless request
does, so the timing includes the connection. Tenants created here expire like any other
demo tenant and are removed by the nightly cleanup.
"""

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv

from bench.run import _settings, _summary
from clinical_ledger.tenancy.seed import load_seed
from clinical_ledger.tenancy.tenants import create_demo_tenant

ROOT = Path(__file__).resolve().parent.parent


def time_creations(database_url: str, count: int) -> dict[str, Any]:
    settings, seed = _settings(), load_seed()
    total: list[int] = []
    create_only: list[int] = []
    for _ in range(count):
        started = time.perf_counter_ns()
        with psycopg.connect(database_url, autocommit=True, connect_timeout=10) as conn:
            connected = time.perf_counter_ns()
            create_demo_tenant(conn, settings, seed)
        finished = time.perf_counter_ns()
        total.append(finished - started)
        create_only.append(finished - connected)
    return {"with_connect": _summary(total), "create_only": _summary(create_only)}


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--label", default="local")
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    result = {"label": args.label, "count": args.count,
              "measured_at": datetime.now(UTC).isoformat(),
              **time_creations(args.database_url, args.count)}
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "bench" / "results" / f"tenant-create-{args.label}-{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), "utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
