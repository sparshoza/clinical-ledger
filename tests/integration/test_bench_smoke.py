import json
from pathlib import Path

import psycopg
import pytest
from bench.load import load
from bench.run import run

pytestmark = pytest.mark.integration


def test_bench_scripts_run_small(
    owner_conn: psycopg.Connection,
    app_dsn: str,
    migrated_db: str,
    clean_tables: None,
    tmp_path: Path,
) -> None:
    info = load(migrated_db, events=2000, versions=500)
    assert info.events == 2000
    assert info.versions == 500
    out = tmp_path / "result.json"
    run(app_dsn, info, out=out, quick=True)
    result = json.loads(out.read_text("utf-8"))
    assert {"append", "latest_read", "as_of", "verify", "environment"} <= set(result)
    assert result["verify"]["full"]["ok"] is True
    assert result["append"]["c1"]["p50_ms"] > 0
