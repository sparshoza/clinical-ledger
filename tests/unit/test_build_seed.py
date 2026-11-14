import json

from clinical_ledger.ledger.hashing import sha256_hex
from clinical_ledger.tenancy.seed import DEFAULT_SEED_PATH, demo_edit_for, load_seed, next_edit
from clinical_ledger.tenancy.seed_builder import PATIENTS_DIR, build_seed

KINDS = {"patient-summary", "imaging-report", "lab-panel"}


def test_build_seed_is_deterministic() -> None:
    assert build_seed(PATIENTS_DIR) == build_seed(PATIENTS_DIR)


def test_committed_seed_matches_builder() -> None:
    committed = json.loads(DEFAULT_SEED_PATH.read_text("utf-8"))
    assert committed == build_seed(PATIENTS_DIR)


def test_seed_shape() -> None:
    seed = load_seed()
    assert len(seed.records) == 75
    assert {record.kind for record in seed.records} == KINDS
    assert {actor.role for actor in seed.actors} == {"clinician", "auditor", "admin"}
    for record in seed.records:
        assert 3 <= len(record.versions) <= 6, record.key
        offsets = [v.created_offset_days for v in record.versions]
        assert offsets == sorted(offsets)
        assert all(offset < 0 for offset in offsets)


def test_seed_blobs_match_their_hashes() -> None:
    seed = load_seed()
    referenced = {v.content_hash for r in seed.records for v in r.versions}
    assert referenced == set(seed.blobs)
    for content_hash, content in seed.blobs.items():
        assert sha256_hex(content) == content_hash


def test_seed_names_are_clearly_synthetic() -> None:
    seed = load_seed()
    summary = next(r for r in seed.records if r.kind == "patient-summary")
    first = json.loads(seed.blobs[summary.versions[0].content_hash])
    assert any(ch.isdigit() for ch in first["patient"]["name"][0]["family"])


def test_next_edit_cycles_per_kind() -> None:
    seed = load_seed()
    edits = seed.demo_edits["lab-panel"]
    assert next_edit(seed, "lab-panel", 1) == edits[0]
    assert next_edit(seed, "lab-panel", 1 + len(edits)) == edits[0]
    assert next_edit(seed, "lab-panel", 2) == edits[1 % len(edits)]
    for kind in KINDS:
        assert seed.demo_edits[kind], kind


def test_every_version_changes_the_content() -> None:
    seed = load_seed()
    for record in seed.records:
        hashes = [v.content_hash for v in record.versions]
        assert len(set(hashes)) == len(hashes), record.key


def test_every_demo_edit_changes_the_document() -> None:
    # Clicking "Add a version" must always produce a visible change, on every record and on
    # every click, or the demo shows an empty comparison.
    seed = load_seed()
    for record in seed.records:
        document = json.loads(seed.blobs[record.versions[-1].content_hash])
        version_no = len(record.versions)
        for _ in range(12):
            _edit, changed = demo_edit_for(seed, record.kind, version_no, document)
            assert changed != document, (record.key, version_no)
            document, version_no = changed, version_no + 1
