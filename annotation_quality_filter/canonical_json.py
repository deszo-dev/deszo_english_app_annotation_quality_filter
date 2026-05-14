"""Canonical JSON for fingerprints (architecture §8.1).

UTF-8, sorted object keys, compact separators, no insignificant whitespace.
"""

from __future__ import annotations

import json
from typing import Any


def dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def encode(payload: Any) -> bytes:
    return dumps(payload).encode("utf-8")
