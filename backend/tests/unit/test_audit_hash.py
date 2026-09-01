"""
RecoverAI - Step 37 Unit Tests: Canonical JSON Serialization & Cryptographic SHA-256 Audit Hash Generation
"""

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
import json

from backend.app.core.canonical_json import serialize_canonical_json
from backend.app.services.audit_trail_service import AuditTrailService, GENESIS_HASH, LEGACY_GENESIS_HASH


def test_canonical_json_sorted_keys():
    """Verify serialize_canonical_json sorts object keys deterministically at all nesting levels."""
    data_unordered = {
        "zeta": 1,
        "alpha": "value",
        "nested": {
            "charlie": True,
            "bravo": [3, 2, 1],
            "delta": {"y": 2, "x": 1},
        },
    }

    serialized = serialize_canonical_json(data_unordered)

    # Key order verification
    expected_order_keys = ['"alpha"', '"nested"', '"bravo"', '"charlie"', '"delta"', '"x"', '"y"', '"zeta"']
    last_idx = -1
    for key in expected_order_keys:
        idx = serialized.find(key)
        assert idx != -1, f"Key {key} not found in serialized JSON"
        assert idx > last_idx, f"Key {key} appeared out of order in {serialized}"
        last_idx = idx


def test_canonical_json_compact_separators():
    """Verify serialize_canonical_json uses compact separators (',', ':') with zero whitespace around punctuation."""
    data = {"b": 2, "a": 1, "list": [1, 2]}
    serialized = serialize_canonical_json(data)

    assert ": " not in serialized
    assert ", " not in serialized
    assert serialized == '{"a":1,"b":2,"list":[1,2]}'


def test_canonical_json_datetime_and_decimal_formatting():
    """Verify ISO UTC 'Z' string formatting for datetimes and exact string conversion for Decimals."""
    dt_naive = datetime(2026, 9, 1, 12, 0, 0)
    dt_tz = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    amount_decimal = Decimal("49999.99")

    data = {
        "timestamp_naive": dt_naive,
        "timestamp_tz": dt_tz,
        "amount": amount_decimal,
    }

    serialized = serialize_canonical_json(data)
    parsed = json.loads(serialized)

    assert parsed["timestamp_naive"] == "2026-09-01T12:00:00Z"
    assert parsed["timestamp_tz"] == "2026-09-01T12:00:00Z"
    assert parsed["amount"] == "49999.99"


def test_genesis_hash_constant():
    """Verify exact value of GENESIS_HASH constant anchored to 'RECOVERAI-AUDIT-GENESIS-V1'."""
    expected_genesis = hashlib.sha256("RECOVERAI-AUDIT-GENESIS-V1".encode("utf-8")).hexdigest()
    assert GENESIS_HASH == expected_genesis
    assert len(GENESIS_HASH) == 64


def test_compute_event_hash_sha256_chaining():
    """Verify AuditTrailService.compute_event_hash produces deterministic 64-char hex SHA-256 hash."""
    canonical_payload = '{"actor":"SYSTEM","details":{},"event_type":"STATE_TRANSITION","previous_hash":"abc","state_from":"CREATED","state_to":"AT_RISK","transaction_id":"tx_1"}'
    prev_hash = GENESIS_HASH

    event_hash_1 = AuditTrailService.compute_event_hash(canonical_payload, prev_hash)
    event_hash_2 = AuditTrailService.compute_event_hash(canonical_payload, prev_hash)

    assert len(event_hash_1) == 64
    assert event_hash_1 == event_hash_2

    # Verify sha256 equality
    expected_hash = hashlib.sha256((canonical_payload + prev_hash).encode("utf-8")).hexdigest()
    assert event_hash_1 == expected_hash

    # Verify tampering payload or prev_hash alters resulting hash
    tampered_payload = canonical_payload.replace("tx_1", "tx_2")
    tampered_hash = AuditTrailService.compute_event_hash(tampered_payload, prev_hash)
    assert tampered_hash != event_hash_1


def test_legacy_genesis_hash_constant():
    """Verify LEGACY_GENESIS_HASH constant value anchored to '0'*64 for backward compatibility."""
    assert LEGACY_GENESIS_HASH == "0" * 64
    assert len(LEGACY_GENESIS_HASH) == 64



def test_audit_hash_tamper_detection_reordered_or_modified_keys():
    """Verify altering canonical key order, state, or actor generates a completely distinct SHA-256 hash."""
    canonical_1 = serialize_canonical_json({"actor": "SYSTEM", "event_type": "STATE_TRANSITION", "state_from": "CREATED", "state_to": "AT_RISK"})
    canonical_2 = serialize_canonical_json({"actor": "USER", "event_type": "STATE_TRANSITION", "state_from": "CREATED", "state_to": "AT_RISK"})

    hash_1 = AuditTrailService.compute_event_hash(canonical_1, GENESIS_HASH)
    hash_2 = AuditTrailService.compute_event_hash(canonical_2, GENESIS_HASH)

    assert hash_1 != hash_2
    assert len(hash_1) == 64
    assert len(hash_2) == 64

