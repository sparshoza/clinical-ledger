"""Rebuild src/clinical_ledger/data/seed.json from fixtures/synthea/patients.

Usage: python scripts/build_seed.py
"""

import json

from clinical_ledger.tenancy.seed import DEFAULT_SEED_PATH
from clinical_ledger.tenancy.seed_builder import PATIENTS_DIR, build_seed


def main() -> None:
    seed = build_seed(PATIENTS_DIR)
    DEFAULT_SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(seed, indent=1, sort_keys=True) + "\n"
    DEFAULT_SEED_PATH.write_text(text, "utf-8", newline="\n")
    versions = sum(len(r["versions"]) for r in seed["records"])
    print(f"wrote {len(seed['records'])} records, {versions} versions to {DEFAULT_SEED_PATH}")


if __name__ == "__main__":
    main()
