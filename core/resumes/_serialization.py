"""Helpers for deterministic resume-domain serialization and hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_dumps(value: Any) -> str:
    """Serialize a value with stable key order and separators."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_json_hash(value: Any, *, length: int = 16) -> str:
    """Return a deterministic short hash for a JSON-serializable value."""
    digest = hashlib.sha256(canonical_json_dumps(value).encode("utf-8")).hexdigest()
    return digest[:length]
