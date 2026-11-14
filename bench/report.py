"""Render the latest benchmark results into docs/benchmarks.md and its chart.

Usage: python -m bench.report
Reads the newest bench/results/<timestamp>.json and the newest
bench/results/tenant-create-<label>-*.json per label.
"""

import json
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "bench" / "results"
DOC = ROOT / "docs" / "benchmarks.md"
CHART = ROOT / "docs" / "img" / "latest-read-latency.svg"
CHART_REF = "img/latest-read-latency.svg"


# Settings that say where a machine is or how it formats dates, not how it performs.
_PRIVATE_SETTINGS = ("timezone", "datestyle", "log_timezone", "lc_")


def _setting(value: str) -> str:
    """'16384 8kB' becomes '128 MB': PostgreSQL reports some sizes in 8 kB pages."""
    number, _, unit = value.partition(" ")
    if unit == "8kB" and number.isdigit():
        mb = int(number) * 8 / 1024
        return f"{mb:g} MB"
    return value


def _ms(value: float) -> str:
    return f"{value:.2f}"


def _row(label: str, s: dict[str, float]) -> str:
    return f"| {label} | {_ms(s['p50_ms'])} | {_ms(s['p95_ms'])} | {_ms(s['p99_ms'])} |"


def _probe_label(count: str) -> str:
    return f"{int(count):,}"


def render_markdown(result: dict[str, Any], tenant_runs: list[dict[str, Any]]) -> str:
    env, loaded, verify = result["environment"], result["loaded"], result["verify"]
    settings = {name: _setting(value)
                for name, value in env["postgres_non_default_settings"].items()
                if not name.lower().startswith(_PRIVATE_SETTINGS)}
    lines = [
        "# Benchmarks",
        "",
        "Every number on this page comes from the scripts in `bench/`. They run against one",
        f"tenant holding {loaded['events']:,} journal entries over {loaded['versions']:,} versions",
        f"of {loaded['records']:,} records, all in a single hash chain. Measured "
        f"{result['measured_at'][:10]}.",
        "",
        f"![Median latency of reading a record's latest version]({CHART_REF})",
        "",
        "Reading the latest version costs the same whether a record has 1 version or 10,000:",
        "the head of each record is kept in its own row, so a read never scans history.",
        "",
        "## Writes",
        "",
        "Adding a version: store the content, insert the version, move the record head and",
        "append a journal entry with its hash, in one transaction. Milliseconds.",
        "",
        "| Writers | p50 | p95 | p99 |",
        "| --- | ---: | ---: | ---: |",
        _row("1 writer", result["append"]["c1"]),
        _row("8 writers, same tenant", result["append"]["c8"]),
        "",
        "Entries in one tenant's journal are written one at a time, because each entry carries",
        "the hash of the one before it. Eight writers on the same tenant therefore queue: each",
        "waits for the others, which is the cost of a single unbroken chain. Writers in",
        "different tenants do not wait for each other.",
        "",
        "## Reads",
        "",
        "A full read fetches the content, checks it against its hash, and appends a",
        "`record.read` entry to the journal. A head lookup is the index query alone.",
        "Milliseconds.",
        "",
        "| Versions on the record | Head lookup p50 | Full read p50 | Full read p95 "
        "| 8 readers p50 | 8 readers p95 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for count, probe in sorted(result["latest_read"].items(), key=lambda kv: int(kv[0])):
        lines.append(
            f"| {_probe_label(count)} | {_ms(probe['head_lookup']['p50_ms'])} "
            f"| {_ms(probe['full_read_c1']['p50_ms'])} | {_ms(probe['full_read_c1']['p95_ms'])} "
            f"| {_ms(probe['full_read_c8']['p50_ms'])} | {_ms(probe['full_read_c8']['p95_ms'])} |"
        )
    lines += [
        "",
        "Reading a record as it stood at a past moment (the version in force at that time):",
        "",
        "| Read | p50 | p95 | p99 |",
        "| --- | ---: | ---: | ---: |",
        _row("As of a past time", result["as_of"]),
        "",
        "## Verification",
        "",
        "Verifying recomputes every entry's hash from its fields and the previous hash, and",
        "rehashes every stored document. Starting from the latest checkpoint (written every",
        "1,000 entries) checks only the entries after it.",
        "",
        "| From | Entries checked | Documents checked | Seconds | Entries per second |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label, key in (("The first entry", "full"), ("The latest checkpoint", "from_checkpoint")):
        v = verify[key]
        lines.append(f"| {label} | {v['events']:,} | {v['blobs']:,} | {v['seconds']:,} "
                     f"| {v['events_per_second']:,} |")
    extra = verify["full"]["events"] - loaded["events"]
    if extra > 0:
        lines += ["", f"The full run checks {extra:,} more entries than were loaded: the "
                  "measurements above",
                  "append journal entries of their own, and those are verified too."]
    lines += ["", "Both runs reported the chain intact.", ""] if all(
        verify[k]["ok"] for k in ("full", "from_checkpoint")) else [
        "", "A run reported a broken chain; these numbers are not valid.", ""]
    if tenant_runs:
        lines += [
            "## Starting a demo",
            "",
            "Creating a demo tenant: 75 records, their versions and a fresh hash chain,",
            "inserted in one transaction. Each run opens its own connection, as a serverless",
            "request does. Milliseconds.",
            "",
            "| Database | Runs | p50 with connect | p95 with connect | p50 insert only |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
        for run in tenant_runs:
            lines.append(
                f"| {run['label']} | {run['count']} | {_ms(run['with_connect']['p50_ms'])} "
                f"| {_ms(run['with_connect']['p95_ms'])} | {_ms(run['create_only']['p50_ms'])} |"
            )
        lines.append("")
    lines += [
        "## Setup",
        "",
        f"- Machine: {env['cpu']}, {env['physical_cores']} cores ({env['logical_cpus']} "
        f"threads), {env['memory_gb']} GB RAM, {env['os']}",
        f"- PostgreSQL {env['postgres']} on the same machine, Python {env['python']}",
        "- Document storage: in process, so object storage network time is not counted.",
        "  The deployed demo stores documents in Cloudflare R2; expect its reads to add",
        "  that round trip.",
        f"- Load: {loaded['load_seconds']} seconds to compute and bulk-copy the data set",
        "- Each timing discards a warm-up of 100 operations, then takes 2,000.",
        "- Concurrent runs use one connection per thread.",
        "",
        "PostgreSQL settings changed from the defaults:",
        "",
        "| Setting | Value |",
        "| --- | --- |",
    ]
    lines += [f"| `{name}` | {value} |" for name, value in settings.items()]
    lines += [
        "",
        "## Reproduce",
        "",
        "```sh",
        "python -m bench.load            # creates clinical_ledger_bench and loads it",
        "python -m bench.run             # writes bench/results/<timestamp>.json",
        "python -m bench.tenant_create   # times 20 demo tenant creations",
        "python -m bench.report          # rewrites this page and its chart",
        "```",
        "",
        "`bench.load` reads `DATABASE_URL_OWNER` and drops and recreates the",
        "`clinical_ledger_bench` database next to it. `bench.run` connects as `ledger_app`,",
        "the same restricted login the application uses.",
        "",
    ]
    return "\n".join(lines)


# Chart geometry, in px.
WIDTH, HEIGHT = 640, 340
LEFT, RIGHT, TOP, BOTTOM = 56, 16, 92, 44
BAR, GAP = 24, 2
SERIES = (("head_lookup", "Head lookup", "s1"), ("full_read_c1", "Full read", "s2"))


def _nice_max(value: float) -> float:
    step = 0.5
    return max(step, step * int(value / step + 1))


def _bar_path(x: float, y: float, height: float) -> str:
    """A column with a 4px rounded top, square at the baseline."""
    r = min(4.0, height, BAR / 2)
    base = y + height
    return (f"M{x:.1f},{base:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
            f"H{x + BAR - r:.1f} Q{x + BAR:.1f},{y:.1f} {x + BAR:.1f},{y + r:.1f} "
            f"V{base:.1f} Z")


def render_svg(result: dict[str, Any]) -> str:
    probes = sorted(result["latest_read"].items(), key=lambda kv: int(kv[0]))
    top = _nice_max(max(p[key]["p50_ms"] for _, p in probes for key, _, _ in SERIES))
    plot_w, plot_h = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM

    def y_of(ms: float) -> float:
        return TOP + plot_h * (1 - ms / top)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" role="img" aria-labelledby="t d">',
        '<title id="t">Reading the latest version stays flat as history grows</title>',
        '<desc id="d">Median milliseconds to read the latest version of a record with 1, '
        "100 and 10,000 versions, for a head lookup and a full read. The full table is in "
        "docs/benchmarks.md.</desc>",
        "<style>",
        "svg{--surface:#ffffff;--ink:#15222b;--ink-2:#4a5d68;--grid:#dde5e0;--axis:#9fb0a6;"
        "--s1:#1c4c9c;--s2:#2f9a5a;font-family:system-ui,-apple-system,'Segoe UI',sans-serif}",
        "@media (prefers-color-scheme:dark){svg{--surface:#0d1117;--ink:#e6edf3;"
        "--ink-2:#a9b6c1;--grid:#26313a;--axis:#4b5a65;--s1:#4f86d9;--s2:#2f9e5f}}",
        ".bg{fill:var(--surface)}.title{fill:var(--ink);font-size:16px;font-weight:600}",
        ".sub,.tick,.value,.legend{fill:var(--ink-2);font-size:12px}",
        ".group{fill:var(--ink);font-size:12px}",
        ".grid{stroke:var(--grid);stroke-width:1}.axis{stroke:var(--axis);stroke-width:1}",
        ".bar.s1{fill:var(--s1)}.bar.s2{fill:var(--s2)}",
        ".sw.s1{fill:var(--s1)}.sw.s2{fill:var(--s2)}",
        ".value{font-variant-numeric:tabular-nums}",
        "</style>",
        f'<rect class="bg" width="{WIDTH}" height="{HEIGHT}" rx="8"/>',
        '<text class="title" x="16" y="28">Reading the latest version stays flat as history '
        "grows</text>",
        '<text class="sub" x="16" y="48">Median milliseconds, one client, 2,000 reads per '
        "bar</text>",
    ]
    legend_x = 16.0
    for _, name, slot in SERIES:
        parts.append(f'<rect class="sw {slot}" x="{legend_x}" y="62" width="12" height="12" '
                     'rx="2"/>')
        parts.append(f'<text class="legend" x="{legend_x + 18}" y="72">{name}</text>')
        legend_x += 18 + 8 * len(name) + 20
    ticks = 4
    for i in range(ticks + 1):
        ms = top * i / ticks
        y = y_of(ms)
        parts.append(f'<line class="{"axis" if i == 0 else "grid"}" x1="{LEFT}" y1="{y:.1f}" '
                     f'x2="{WIDTH - RIGHT}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{LEFT - 8}" y="{y + 4:.1f}" '
                     f'text-anchor="end">{ms:g}</text>')
    group_w = plot_w / len(probes)
    pair_w = BAR * len(SERIES) + GAP * (len(SERIES) - 1)
    for g, (count, probe) in enumerate(probes):
        center = LEFT + group_w * (g + 0.5)
        x = center - pair_w / 2
        for key, name, slot in SERIES:
            ms = probe[key]["p50_ms"]
            y = y_of(ms)
            label = f"{_probe_label(count)} versions, {name.lower()}: {ms:.2f} ms median"
            parts.append(f'<path class="bar {slot}" d="{_bar_path(x, y, y_of(0) - y)}">'
                         f"<title>{escape(label)}</title></path>")
            parts.append(f'<text class="value" x="{x + BAR / 2:.1f}" y="{y - 6:.1f}" '
                         f'text-anchor="middle">{ms:.2f}</text>')
            x += BAR + GAP
        noun = "version" if count == "1" else "versions"
        parts.append(f'<text class="group" x="{center:.1f}" y="{HEIGHT - BOTTOM + 22}" '
                     f'text-anchor="middle">{_probe_label(count)} {noun}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _latest_tenant_runs() -> list[dict[str, Any]]:
    newest: dict[str, Path] = {}
    for path in sorted(RESULTS.glob("tenant-create-*.json")):
        newest[json.loads(path.read_text("utf-8"))["label"]] = path
    return [json.loads(p.read_text("utf-8")) for p in newest.values()]


def main() -> None:
    runs = sorted(RESULTS.glob("2*.json"))
    if not runs:
        raise SystemExit("no results yet: run python -m bench.run first")
    result = json.loads(runs[-1].read_text("utf-8"))
    DOC.parent.mkdir(parents=True, exist_ok=True)
    CHART.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text(render_markdown(result, _latest_tenant_runs()), "utf-8", newline="\n")
    CHART.write_text(render_svg(result), "utf-8", newline="\n")
    print(f"wrote {DOC.relative_to(ROOT)} and {CHART.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
