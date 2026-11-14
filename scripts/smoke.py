"""Check a running deployment end to end, the way a visitor uses it.

Usage: python scripts/smoke.py https://clinical-ledger-weld.vercel.app [--cron-secret SECRET]
Prints PASS or FAIL per check and exits non-zero if any check fails. With
--cron-secret it also calls the nightly cleanup once (it only removes expired demos).
"""

import argparse
import sys
from collections.abc import Callable
from typing import Any

import httpx

API = "/api/v1"


class Smoke:
    def __init__(self, base_url: str) -> None:
        self.http = httpx.Client(base_url=base_url.rstrip("/"), timeout=60)
        self.failures = 0
        self.token = ""

    def check(self, name: str, test: Callable[[], str | None]) -> None:
        try:
            detail = test()
        except Exception as exc:  # noqa: BLE001 - a smoke test reports every failure
            self.failures += 1
            print(f"FAIL  {name}: {exc}")
            return
        print(f"PASS  {name}{f' ({detail})' if detail else ''}")

    def call(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = self.http.request(method, f"{API}{path}", headers=headers, **kwargs)
        if response.status_code >= 400:
            raise AssertionError(
                f"{method} {path} returned {response.status_code}: {response.text[:200]}"
            )
        return response.json()


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run(base_url: str, cron_secret: str | None) -> int:
    s = Smoke(base_url)
    state: dict[str, Any] = {}

    def page() -> str:
        response = s.http.get("/", headers={"Accept": "text/html"})
        expect(response.status_code == 200, f"status {response.status_code}")
        expect("Clinical Ledger" in response.text, "page title missing")
        return "demo page served"

    def health() -> str:
        body = s.call("GET", "/health")
        expect(body["status"] == "ok", str(body))
        return f"database {body['database']}, storage {body['storage']}"

    def sign_in() -> str:
        body = s.call("POST", "/auth/demo", json={"role": "admin"})
        s.token = body["token"]
        return f"tenant {body['tenant_id'][:8]}"

    def records() -> str:
        body = s.call("GET", "/records")
        expect(len(body["items"]) > 0, "no records")
        state["record"] = body["items"][0]
        return f"{len(body['items'])} on the first page"

    def read_content() -> str:
        record = state["record"]
        s.call("GET", f"/records/{record['id']}")
        return "content read and checked against its hash"

    def add_version() -> str:
        record = state["record"]
        body = s.call("POST", f"/records/{record['id']}/demo-edit")
        expect(body["version_no"] == record["latest_version_no"] + 1, str(body))
        return f"version {body['version_no']}"

    def verify_intact() -> str:
        body = s.call("POST", "/verify", json={})
        expect(body["ok"] is True, str(body))
        return f"{body['checked_events']} entries"

    def tamper_and_catch() -> str:
        tamper = s.call("POST", "/demo/tamper", json={"mode": "event"})
        body = s.call("POST", "/verify", json={})
        expect(body["ok"] is False, "tampering was not caught")
        expect(body["first_broken_seq"] == tamper["target_seq"], str(body))
        return f"broken at #{body['first_broken_seq']}"

    def reset() -> str:
        body = s.call("POST", "/demo/reset")
        s.token = body["token"]
        verified = s.call("POST", "/verify", json={})
        expect(verified["ok"] is True, str(verified))
        return "fresh ledger verifies"

    checks: list[tuple[str, Callable[[], str | None]]] = [
        ("demo page", page),
        ("health", health),
        ("demo sign-in", sign_in),
        ("list records", records),
        ("read a record", read_content),
        ("add a version", add_version),
        ("verify intact chain", verify_intact),
        ("tamper is caught", tamper_and_catch),
        ("reset", reset),
    ]
    if cron_secret:

        def cleanup() -> str:
            response = s.http.get(
                f"{API}/cron/cleanup", headers={"Authorization": f"Bearer {cron_secret}"}
            )
            expect(response.status_code == 200, f"status {response.status_code}")
            return f"removed {response.json()['removed']}"

        checks.append(("nightly cleanup", cleanup))

    for name, test in checks:
        s.check(name, test)
    print("ALL PASS" if s.failures == 0 else f"{s.failures} FAILED")
    return 1 if s.failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--cron-secret")
    args = parser.parse_args()
    sys.exit(run(args.base_url, args.cron_secret))


if __name__ == "__main__":
    main()
