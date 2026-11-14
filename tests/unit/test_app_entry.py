import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from clinical_ledger.main import create_app
from tests.conftest import make_settings


def test_entry_point_is_a_fastapi_app_that_imports_without_environment() -> None:
    # Hosts that detect the app (and promote its static frontend) need a real FastAPI
    # instance at import time, before any secret is read.
    code = (
        "import os, fastapi\n"
        "for key in list(os.environ):\n"
        "    if key.startswith(('DATABASE_', 'S3_', 'JWT_', 'CRON_')): del os.environ[key]\n"
        "from clinical_ledger.main import app\n"
        "assert isinstance(app, fastapi.FastAPI)\n"
    )
    root = Path(__file__).resolve().parents[2]
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], cwd=Path("/"), capture_output=True, text=True,
        env={"PYTHONPATH": str(root / "src"), "SYSTEMROOT": "C:\\Windows", "PATH": ""},
        check=False,
    )
    assert done.returncode == 0, done.stderr


def test_built_frontend_is_served_at_the_root_and_api_still_wins(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<!doctype html><title>Clinical Ledger</title>")
    app = create_app(make_settings(), web_dist=tmp_path)
    assert isinstance(app, FastAPI)
    with TestClient(app) as client:
        page = client.get("/", headers={"Accept": "text/html"})
        assert page.status_code == 200
        assert "Clinical Ledger" in page.text
        assert client.get("/api/openapi.json").status_code == 200
