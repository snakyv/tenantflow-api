from app.infra.idempotency import canonical_request_hash


def test_hash_is_independent_of_json_key_order() -> None:
    assert canonical_request_hash({"a": 1, "b": 2}) == canonical_request_hash({"b": 2, "a": 1})


def test_hash_changes_when_semantics_change() -> None:
    assert canonical_request_hash({"plan": "pro"}) != canonical_request_hash({"plan": "business"})
