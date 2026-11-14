"""Write the API's OpenAPI schema to web/openapi.json (no server or database needed).

Usage: python scripts/export_openapi.py
"""

import json
from pathlib import Path

from clinical_ledger.main import create_app
from clinical_ledger.settings import Settings

OUT = Path(__file__).resolve().parent.parent / "web" / "openapi.json"


def main() -> None:
    # Placeholder values: only the schema is generated, nothing connects anywhere.
    required = (
        "s3_bucket",
        "s3_access_key_id",
        "s3_secret_access_key",
        "jwt_secret",
        "cron_secret",
    )
    placeholders: dict[str, str] = dict.fromkeys(required, "unused")
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url="postgresql://unused@localhost/unused",
        **placeholders,
    )
    schema = create_app(settings).openapi()
    OUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", "utf-8", newline="\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
