"""Deterministic benchmark content, so any script can rebuild any version's bytes."""

from clinical_ledger.ledger.content import encode_document


def content_for(record_index: int, version_no: int) -> bytes:
    return encode_document(
        {
            "resourceType": "Observation",
            "record": record_index,
            "version": version_no,
            "status": "final",
            "note": "synthetic benchmark document",
        }
    )
