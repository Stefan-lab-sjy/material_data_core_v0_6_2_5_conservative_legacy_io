from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import re
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    import uuid
    return f"{prefix}_{uuid.uuid4().hex}"


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_path(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def gcd_many(values: list[int]) -> int:
    g = 0
    for v in values:
        g = math.gcd(g, int(v))
    return max(g, 1)


def formula_from_symbols_counts(symbols: list[str], counts: list[int]) -> str | None:
    if not symbols or len(symbols) != len(counts):
        return None
    g = gcd_many(counts)
    parts: list[str] = []
    for symbol, count in zip(symbols, counts):
        n = count // g
        parts.append(symbol)
        if n != 1:
            parts.append(str(n))
    return ''.join(parts)


def normalized_formula(formula: str | None) -> str | None:
    if not formula:
        return None
    return re.sub(r"\s+", "", formula)
