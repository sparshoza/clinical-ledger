"""Build the demo seed set from the trimmed Synthea fixtures.

Each patient yields three records (patient summary, imaging report, lab panel), each
with 3 to 6 versions produced by realistic edits. The output is deterministic so the
committed seed file can be checked against a rebuild.
"""

import base64
import copy
import json
import uuid
from pathlib import Path
from typing import Any

from clinical_ledger.ledger.content import encode_document
from clinical_ledger.ledger.hashing import sha256_hex

ROOT = Path(__file__).resolve().parents[3]
PATIENTS_DIR = ROOT / "fixtures" / "synthea" / "patients"
MEDIA_TYPE = "application/json"
DAY_STEP = 20

ACTORS = [
    {"role": "clinician", "display_name": "Demo Clinician"},
    {"role": "auditor", "display_name": "Demo Auditor"},
    {"role": "admin", "display_name": "Demo Admin"},
]

DEMO_EDITS: dict[str, list[dict[str, Any]]] = {
    "patient-summary": [
        {
            "description": "Added condition: Seasonal allergic rhinitis",
            "json_patch": [
                {
                    "op": "add",
                    "path": "/conditions/-",
                    "value": {
                        "resourceType": "Condition",
                        "id": "demo-allergic-rhinitis",
                        "code": {"display": "Seasonal allergic rhinitis"},
                        "clinicalStatus": "active",
                        "onsetDateTime": "2026-11-01T09:00:00Z",
                    },
                }
            ],
        },
        {
            "description": "Marked the first listed condition as resolved",
            "json_patch": [
                {"op": "replace", "path": "/conditions/0/clinicalStatus", "value": "resolved"}
            ],
        },
    ],
    "lab-panel": [
        {
            "description": "Added lab result: Hemoglobin A1c 5.9 %",
            "json_patch": [
                {
                    "op": "add",
                    "path": "/observations/-",
                    "value": {
                        "resourceType": "Observation",
                        "id": "demo-hba1c",
                        "code": {"display": "Hemoglobin A1c/Hemoglobin.total in Blood"},
                        "effectiveDateTime": "2026-11-01T09:00:00Z",
                        "valueQuantity": {"value": 5.9, "unit": "%"},
                    },
                }
            ],
        },
        {
            "description": "Added lab result: LDL cholesterol 98 mg/dL",
            "json_patch": [
                {
                    "op": "add",
                    "path": "/observations/-",
                    "value": {
                        "resourceType": "Observation",
                        "id": "demo-ldl",
                        "code": {"display": "Low Density Lipoprotein Cholesterol"},
                        "effectiveDateTime": "2026-11-01T09:00:00Z",
                        "valueQuantity": {"value": 98, "unit": "mg/dL"},
                    },
                }
            ],
        },
    ],
    "imaging-report": [
        {
            "description": "Amended the report",
            "json_patch": [{"op": "replace", "path": "/report/status", "value": "amended"}],
        },
        {
            "description": "Added an addendum to the conclusion",
            "json_patch": [
                {
                    "op": "add",
                    "path": "/report/conclusion",
                    "value": "Addendum: compared with the prior study, no interval change.",
                }
            ],
        },
    ],
}


def _condition_name(condition: dict[str, Any]) -> str:
    return str(condition["code"].get("display") or "condition")


def _summary_versions(patient: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
    conditions = patient["conditions"]
    document = {"patient": patient["patient"], "conditions": conditions[:1]}
    versions = [(copy.deepcopy(document), "Initial record")]
    for condition in conditions[1:5]:
        document["conditions"] = [*document["conditions"], condition]
        versions.append((copy.deepcopy(document), f"Added condition: {_condition_name(condition)}"))
    first = document["conditions"][0]
    resolved = {**first, "clinicalStatus": "resolved"}
    document["conditions"] = [resolved, *document["conditions"][1:]]
    versions.append((copy.deepcopy(document), f"Marked {_condition_name(first)} as resolved"))
    return versions


def _lab_versions(patient: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
    observations = patient["observations"]
    document = {"observations": observations[:2]}
    versions = [(copy.deepcopy(document), "Initial lab panel")]
    for observation in observations[2:6]:
        document["observations"] = [*document["observations"], observation]
        name = observation["code"].get("display") or "lab result"
        versions.append((copy.deepcopy(document), f"Added lab result: {name}"))
    return versions


def _report_versions(patient: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
    report = dict(patient["report"])
    first = {"report": {**report, "status": "preliminary"}}
    second = {"report": {**report, "status": "preliminary", "conclusion": "No acute findings."}}
    third = {"report": {**report, "status": "final", "conclusion": "No acute findings."}}
    return [
        (first, "Preliminary report"),
        (second, "Added conclusion"),
        (third, "Report finalized"),
    ]


def build_seed(patients_dir: Path) -> dict[str, Any]:
    blobs: dict[str, str] = {}
    records: list[dict[str, Any]] = []
    builders = [
        ("patient-summary", _summary_versions),
        ("imaging-report", _report_versions),
        ("lab-panel", _lab_versions),
    ]
    for path in sorted(patients_dir.glob("*.json")):
        patient = json.loads(path.read_text("utf-8"))
        patient_id = patient["patient"]["id"]
        for kind, builder in builders:
            documents = builder(patient)[:6]
            count = len(documents)
            versions = []
            for index, (document, note) in enumerate(documents):
                content = encode_document(document)
                content_hash = sha256_hex(content)
                blobs[content_hash] = base64.b64encode(content).decode("ascii")
                versions.append(
                    {
                        "content_hash": content_hash,
                        "media_type": MEDIA_TYPE,
                        "note": note,
                        "created_offset_days": -DAY_STEP * (count - index),
                    }
                )
            records.append(
                {
                    "key": f"{patient_id}:{kind}",
                    "kind": kind,
                    "subject_ref": f"Patient/{patient_id}",
                    "versions": versions,
                }
            )
    actors = [
        {**actor, "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"clinical-ledger:{actor['role']}"))}
        for actor in ACTORS
    ]
    return {
        "actors": actors,
        "records": records,
        "demo_edits": DEMO_EDITS,
        "blobs": dict(sorted(blobs.items())),
    }
