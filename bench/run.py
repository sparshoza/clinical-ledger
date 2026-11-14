"""Measure the loaded benchmark tenant through the application's own code paths.

Usage: python -m bench.run [--quick]
Reads bench/results/loaded.json (written by bench.load) and writes
bench/results/<timestamp>.json. Storage is in-process (the content is rebuilt from
bench.content), so timings cover the database and the application, not network storage.
"""

import argparse
import functools
import json
import os
import platform
import statistics
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import UUID

import psutil
import psycopg
from dotenv import load_dotenv

from bench.content import content_for
from bench.load import INFO_PATH, BenchInfo, record_plan
from clinical_ledger.db import tenant_transaction
from clinical_ledger.ledger.hashing import sha256_hex
from clinical_ledger.ledger.models import Actor
from clinical_ledger.ledger.reader import LedgerReader
from clinical_ledger.ledger.verify import verify_chain
from clinical_ledger.ledger.writer import LedgerWriter
from clinical_ledger.settings import Settings
from clinical_ledger.storage.blobs import InMemoryBlobStore, blob_key

ROOT = Path(__file__).resolve().parent.parent


def _settings() -> Settings:
    placeholders: dict[str, Any] = dict.fromkeys(
        ("s3_bucket", "s3_access_key_id", "s3_secret_access_key", "jwt_secret", "cron_secret"),
        "unused",
    )
    return Settings(_env_file=None, database_url="unused", s3_backend="memory",  # type: ignore[call-arg]
                    **placeholders)


def _summary(samples_ns: list[int]) -> dict[str, float]:
    ms = sorted(n / 1e6 for n in samples_ns)
    def pct(p: float) -> float:
        return round(ms[min(len(ms) - 1, int(p * len(ms)))], 3)
    return {"ops": len(ms), "p50_ms": pct(0.50), "p95_ms": pct(0.95), "p99_ms": pct(0.99),
            "mean_ms": round(statistics.fmean(ms), 3)}


def _timed(op: Callable[[], Any], count: int) -> list[int]:
    warmup = max(5, count // 20)
    samples = []
    for i in range(count + warmup):
        started = time.perf_counter_ns()
        op()
        if i >= warmup:
            samples.append(time.perf_counter_ns() - started)
    return samples


def _concurrent(make_op: Callable[[psycopg.Connection], Callable[[], Any]], dsn: str,
                threads: int, per_thread: int) -> list[int]:
    results: list[list[int]] = [[] for _ in range(threads)]
    errors: list[BaseException] = []

    def worker(n: int) -> None:
        try:
            with psycopg.connect(dsn, autocommit=True) as conn:
                results[n] = _timed(make_op(conn), per_thread)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    pool = [threading.Thread(target=worker, args=(n,)) for n in range(threads)]
    for thread in pool:
        thread.start()
    for thread in pool:
        thread.join()
    if errors:
        raise errors[0]
    return [s for r in results for s in r]


# Settings that are configuration noise rather than performance, left out of the report.
_SETTING_NOISE = ("log", "lc_", "port", "listen", "datestyle", "timezone", "default_text",
                  "dynamic_shared", "ssl", "hba", "ident", "config_file", "data_directory",
                  "cluster_name", "application_name", "client_encoding")


def _cpu_name() -> str:
    """The marketing name where the OS exposes it; platform.processor() is a family code."""
    if platform.system() == "Windows":
        import winreg

        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    else:
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.exists():
            for line in cpuinfo.read_text("utf-8").splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    return platform.processor() or platform.machine()


def _environment(conn: psycopg.Connection) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT name, setting, coalesce(unit, '') FROM pg_settings "
        "WHERE source NOT IN ('default', 'override', 'client', 'session') ORDER BY name"
    ).fetchall()
    settings = {name: f"{setting}{' ' + unit if unit else ''}" for name, setting, unit in rows
                if not name.lower().startswith(_SETTING_NOISE)}
    return {
        "python": platform.python_version(),
        "os": f"{platform.system()} {platform.release()}",
        "cpu": _cpu_name(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cpus": psutil.cpu_count(),
        "memory_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "postgres": conn.execute("SHOW server_version").fetchone()[0],  # type: ignore[index]
        "postgres_non_default_settings": settings,
        "storage": "in-process (content rebuilt from bench.content)",
    }


def run(app_dsn: str, info: BenchInfo, out: Path, quick: bool = False) -> dict[str, Any]:
    tenant, actor = UUID(info.tenant_id), Actor(UUID(info.actor_id), "clinician")
    settings, store = _settings(), InMemoryBlobStore()
    for index, count in enumerate(record_plan(info.versions)):
        for version in range(1, count + 1):
            data = content_for(index, version)
            store.put(blob_key(sha256_hex(data)), data, "application/json")
    n = 16 if quick else 2000
    probes = {int(k): UUID(v) for k, v in info.probe_records.items()}
    hot = probes[max(probes)]
    with psycopg.connect(app_dsn, autocommit=True) as conn, tenant_transaction(conn, tenant):
        present = conn.execute("SELECT count(*) FROM versions").fetchone()[0]  # type: ignore[index]
        if present != info.versions:
            raise SystemExit("this data set has been measured already: run python -m bench.load "
                             "again first")
        # Appends go to an ordinary record, so the probe records keep their version counts.
        append_target = conn.execute(
            "SELECT record_id FROM record_heads WHERE NOT (record_id = ANY(%s)) "
            "ORDER BY record_id LIMIT 1", (list(probes.values()),)).fetchone()[0]  # type: ignore[index]
    counter = iter(range(10**9))

    def make_reader(conn: psycopg.Connection) -> LedgerReader:
        writer = LedgerWriter(conn, store, tenant, actor, settings)
        return LedgerReader(conn, store, tenant, actor, writer)

    def append_op(conn: psycopg.Connection) -> Callable[[], Any]:
        writer = LedgerWriter(conn, store, tenant, actor, settings)
        def op() -> None:
            with tenant_transaction(conn, tenant):
                content = f'{{"bench":{next(counter)}}}'.encode()
                writer.add_version(append_target, content, "application/json")
        return op

    def head_op(conn: psycopg.Connection, record: UUID) -> Callable[[], Any]:
        def op() -> None:
            with tenant_transaction(conn, tenant):
                conn.execute("SELECT latest_version_no, latest_content_hash FROM record_heads "
                             "WHERE tenant_id = %s AND record_id = %s", (tenant, record)).fetchone()
        return op

    def read_op(conn: psycopg.Connection, record: UUID) -> Callable[[], Any]:
        reader = make_reader(conn)
        def op() -> None:
            with tenant_transaction(conn, tenant):
                reader.latest(record)
        return op

    result: dict[str, Any] = {"loaded": {"events": info.events, "versions": info.versions,
                                         "records": info.record_count,
                                         "load_seconds": info.load_seconds},
                              "measured_at": datetime.now(UTC).isoformat()}
    with psycopg.connect(app_dsn, autocommit=True) as conn:
        result["environment"] = _environment(conn)
        result["append"] = {"c1": _summary(_timed(append_op(conn), n)),
                            "c8": _summary(_concurrent(append_op, app_dsn, 8, n // 8))}
        result["latest_read"] = {}
        for count, record in sorted(probes.items()):
            result["latest_read"][str(count)] = {
                "head_lookup": _summary(_timed(head_op(conn, record), n)),
                "full_read_c1": _summary(_timed(read_op(conn, record), n)),
                "full_read_c8": _summary(
                    _concurrent(functools.partial(read_op, record=record), app_dsn, 8, n // 8)),
            }
        reader = make_reader(conn)
        with tenant_transaction(conn, tenant):
            middle = conn.execute(
                "SELECT created_at FROM versions WHERE tenant_id = %s AND record_id = %s "
                "AND version_no = %s", (tenant, hot, max(probes) // 2 or 1)).fetchone()[0]  # type: ignore[index]
        def as_of_op() -> None:
            with tenant_transaction(conn, tenant):
                reader.as_of(hot, middle)
        result["as_of"] = _summary(_timed(as_of_op, n))
        result["verify"] = {}
        for mode, from_checkpoint in (("full", False), ("from_checkpoint", True)):
            started = time.perf_counter()
            with tenant_transaction(conn, tenant):
                verified = verify_chain(conn, store, tenant, from_checkpoint=from_checkpoint)
            seconds = time.perf_counter() - started
            result["verify"][mode] = {"ok": verified.ok, "events": verified.checked_events,
                                      "blobs": verified.checked_blobs, "seconds": round(seconds, 3),
                                      "events_per_second": round(verified.checked_events / seconds)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), "utf-8")
    return result


def app_dsn_for(owner_dsn: str) -> str:
    load_dotenv(ROOT / ".env")
    parts = urlsplit(owner_dsn)
    netloc = f"ledger_app:{quote(os.environ['LEDGER_APP_PASSWORD'], safe='')}@{parts.hostname}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    info = BenchInfo(**json.loads(INFO_PATH.read_text("utf-8")))
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "bench" / "results" / f"{stamp}.json"
    run(app_dsn_for(info.owner_dsn), info, out, quick=args.quick)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
