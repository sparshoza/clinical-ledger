"""Write the API's OpenAPI schema to web/openapi.json (no server or database needed).

Usage: python scripts/export_openapi.py
"""

import json
from pathlib import Path

from clinical_ledger.main import create_app
from clinical_ledger.settings import Settings

OUT = Path(__file__).resolve().parent.parent / "web" / "openapi.json"


def main() -> None:
    settings = Settings(  # placeholder values: only the schema is generated
        _env_file=None,  # type: ignore[call-arg]
        database_url="postgresql://unused@localhost/unused",
        s3_bucket="unused",
        s3_access_key_id="unused",
        s3_secret_access_key="unused",
        jwt_secret="unused",
        cron_secret="unused",
    )
    schema = create_app(settings).openapi()
    OUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", "utf-8", newline="\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
