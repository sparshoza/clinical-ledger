"""Deployment entry point: the hosting platform loads `app` from this file."""

import sys
from pathlib import Path

# The package lives in src/; make it importable whether or not it is installed.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from clinical_ledger.main import app  # noqa: E402

__all__ = ["app"]
