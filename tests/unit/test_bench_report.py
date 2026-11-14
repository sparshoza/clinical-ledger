import xml.etree.ElementTree as ET
from typing import Any

from bench.report import render_markdown, render_svg

SVG = "{http://www.w3.org/2000/svg}"


def _summary(p50: float) -> dict[str, float]:
    return {"ops": 2000, "p50_ms": p50, "p95_ms": p50 * 2, "p99_ms": p50 * 3, "mean_ms": p50}


def _result() -> dict[str, Any]:
    probe = {
        "head_lookup": _summary(0.3),
        "full_read_c1": _summary(1.2),
        "full_read_c8": _summary(6.0),
    }
    return {
        "loaded": {
            "events": 2_000_000,
            "versions": 500_000,
            "records": 48_993,
            "load_seconds": 147.4,
        },
        "measured_at": "2026-11-14T13:29:26+00:00",
        "environment": {
            "python": "3.12.3",
            "os": "Windows 11",
            "cpu": "Intel64",
            "physical_cores": 14,
            "logical_cpus": 20,
            "memory_gb": 31.7,
            "postgres": "16.15",
            "postgres_non_default_settings": {
                "shared_buffers": "16384 8kB",
                "TimeZone": "Asia/Calcutta",
            },
            "storage": "in-process",
        },
        "append": {"c1": _summary(1.5), "c8": _summary(21.9)},
        "latest_read": {"1": probe, "100": probe, "10000": probe},
        "as_of": _summary(1.4),
        "verify": {
            "full": {
                "ok": True,
                "events": 2_018_884,
                "blobs": 504_196,
                "seconds": 84.9,
                "events_per_second": 23_775,
            },
            "from_checkpoint": {
                "ok": True,
                "events": 884,
                "blobs": 0,
                "seconds": 0.115,
                "events_per_second": 7_690,
            },
        },
    }


def test_markdown_carries_every_measurement() -> None:
    text = render_markdown(_result(), tenant_runs=[])
    assert "| 1 writer | 1.50 | 3.00 | 4.50 |" in text
    assert "| 10,000 |" in text
    assert "2,018,884" in text
    assert "| `shared_buffers` | 128 MB |" in text
    assert "TimeZone" not in text  # where the machine is stays private
    assert "18,884 more entries" in text
    assert "python -m bench.load" in text
    assert "—" not in text  # no em dashes in published copy


def test_markdown_includes_tenant_creation_when_measured() -> None:
    run = {
        "label": "neon",
        "count": 20,
        "with_connect": _summary(400.0),
        "create_only": _summary(300.0),
    }
    assert "| neon | 20 | 400.00 |" in render_markdown(_result(), tenant_runs=[run])


def test_svg_has_one_bar_per_probe_and_series() -> None:
    root = ET.fromstring(render_svg(_result()))  # noqa: S314 (our own output)
    bars = [el for el in root.iter(f"{SVG}path") if el.get("class", "").startswith("bar ")]
    assert len(bars) == 6
    assert all(bar.find(f"{SVG}title") is not None for bar in bars)
    assert root.find(f"{SVG}title") is not None
