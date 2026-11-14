from datetime import UTC, datetime, timedelta, timezone

import pytest

from clinical_ledger.ledger.hashing import (
    GENESIS_HASH,
    canonical_json,
    compute_event_hash,
    format_ts,
    sha256_hex,
)


def test_canonical_json_sorts_keys_and_strips_whitespace() -> None:
    assert canonical_json({"b": 1, "a": [True, None]}) == b'{"a":[true,null],"b":1}'


def test_canonical_json_keeps_unicode() -> None:
    assert canonical_json({"name": "José"}) == '{"name":"José"}'.encode()


@pytest.mark.parametrize("value", [{"x": 1.5}, {"a": {"b": 0.1}}, {"a": [1, 2.0]}])
def test_canonical_json_rejects_floats(value: object) -> None:
    with pytest.raises(TypeError):
        canonical_json(value)


def test_format_ts_converts_to_utc_microseconds() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    assert format_ts(datetime(2026, 1, 2, 10, 0, 0, 5, tzinfo=ist)) == "2026-01-02T04:30:00.000005Z"


def test_format_ts_rejects_naive() -> None:
    with pytest.raises(ValueError):
        format_ts(datetime(2026, 1, 2, 10, 0, 0))


def test_canonical_json_formats_datetimes() -> None:
    when = datetime(2026, 1, 2, 4, 30, tzinfo=UTC)
    assert canonical_json({"at": when}) == b'{"at":"2026-01-02T04:30:00.000000Z"}'


def test_genesis_hash_is_64_zeros() -> None:
    assert GENESIS_HASH == "0" * 64


def test_event_hash_known_vector() -> None:
    fields = {"seq": 1, "event_type": "record.created"}
    expected = sha256_hex(
        GENESIS_HASH.encode() + canonical_json({"event_type": "record.created", "seq": 1})
    )
    assert compute_event_hash(GENESIS_HASH, fields) == expected


def test_event_hash_changes_with_prev_hash() -> None:
    fields = {"seq": 2, "event_type": "version.added"}
    assert compute_event_hash(GENESIS_HASH, fields) != compute_event_hash("f" * 64, fields)
