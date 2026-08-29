"""
RecoverAI - Canonical JSON Serializer (Step 23)

Provides deterministic, compact, sorted-key JSON serialization for SHA-256 cryptographic audit chaining.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


def _canonical_default_encoder(obj: Any) -> Any:
    """Default encoder for non-standard JSON types ensuring deterministic string representation."""
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        else:
            obj = obj.astimezone(timezone.utc)
        return obj.isoformat().replace("+00:00", "Z")
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "dict"):
        return obj.dict()
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return str(obj)


def serialize_canonical_json(data: Any) -> str:
    """Serialize data into a deterministic, compact canonical JSON string.

    Rules enforced:
      - Sorted keys at all levels (`sort_keys=True`)
      - Compact separators `(',', ':')` (no extra whitespace around key/value pairs)
      - Datetimes formatted as ISO UTC strings ending in 'Z'
      - Decimals converted to exact string representations
      - UTF-8 clean string output (`ensure_ascii=False`)

    Args:
        data: Python dict, list, scalar, or serializable object.

    Returns:
        Canonical JSON string.
    """
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        default=_canonical_default_encoder,
        ensure_ascii=False,
    )
