"""Extract a small, trimmed fixture set from a Synthea FHIR R4 sample zip.

Usage: python scripts/import_synthea.py <synthea_sample_data_fhir.zip> [--count 25]

Writes fixtures/synthea/patients/<patient-id>.json, each holding only the resources the
demo uses (Patient, Conditions, laboratory Observations, one DiagnosticReport) with
noisy fields removed. Synthea data is synthetic; see fixtures/synthea/NOTICE.
"""

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "fixtures" / "synthea" / "patients"


def _coding(concept: dict[str, Any] | None) -> dict[str, Any]:
    if not concept:
        return {}
    coding = (concept.get("coding") or [{}])[0]
    return {
        "system": coding.get("system"),
        "code": coding.get("code"),
        "display": coding.get("display") or concept.get("text"),
    }


def _patient(resource: dict[str, Any]) -> dict[str, Any]:
    name = (resource.get("name") or [{}])[0]
    address = (resource.get("address") or [{}])[0]
    return {
        "resourceType": "Patient",
        "id": resource["id"],
        "name": [{"family": name.get("family"), "given": name.get("given", [])}],
        "gender": resource.get("gender"),
        "birthDate": resource.get("birthDate"),
        "address": [{"city": address.get("city"), "state": address.get("state")}],
    }


def _condition(resource: dict[str, Any]) -> dict[str, Any]:
    status = _coding(resource.get("clinicalStatus")).get("code")
    return {
        "resourceType": "Condition",
        "id": resource["id"],
        "code": _coding(resource.get("code")),
        "clinicalStatus": status,
        "onsetDateTime": resource.get("onsetDateTime"),
    }


def _observation(resource: dict[str, Any]) -> dict[str, Any]:
    quantity = resource.get("valueQuantity") or {}
    return {
        "resourceType": "Observation",
        "id": resource["id"],
        "code": _coding(resource.get("code")),
        "effectiveDateTime": resource.get("effectiveDateTime"),
        "valueQuantity": {"value": quantity.get("value"), "unit": quantity.get("unit")},
    }


def _report(resource: dict[str, Any]) -> dict[str, Any]:
    return {
        "resourceType": "DiagnosticReport",
        "id": resource["id"],
        "status": "preliminary",
        "code": _coding(resource.get("code")),
        "effectiveDateTime": resource.get("effectiveDateTime"),
    }


def _is_lab(resource: dict[str, Any]) -> bool:
    for category in resource.get("category") or []:
        for coding in category.get("coding") or []:
            if coding.get("code") == "laboratory":
                return "valueQuantity" in resource
    return False


def trim_bundle(bundle: dict[str, Any]) -> dict[str, Any] | None:
    resources = [entry["resource"] for entry in bundle.get("entry", [])]
    patients = [r for r in resources if r.get("resourceType") == "Patient"]
    if not patients:
        return None
    conditions = [r for r in resources if r.get("resourceType") == "Condition"]
    labs = [r for r in resources if r.get("resourceType") == "Observation" and _is_lab(r)]
    reports = [r for r in resources if r.get("resourceType") == "DiagnosticReport"]
    if len(conditions) < 2 or len(labs) < 4 or not reports:
        return None
    return {
        "patient": _patient(patients[0]),
        "conditions": [_condition(r) for r in conditions[:6]],
        "observations": [_observation(r) for r in labs[-6:]],
        "report": _report(reports[-1]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--count", type=int, default=25)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    with zipfile.ZipFile(args.zip_path) as archive:
        for name in sorted(archive.namelist()):
            if written >= args.count:
                break
            if not name.endswith(".json") or "Information" in name:
                continue
            trimmed = trim_bundle(json.loads(archive.read(name)))
            if trimmed is None:
                continue
            target = OUT / f"{trimmed['patient']['id']}.json"
            target.write_text(json.dumps(trimmed, indent=2, sort_keys=True) + "\n", "utf-8")
            written += 1
    print(f"wrote {written} patients to {OUT}")


if __name__ == "__main__":
    main()
