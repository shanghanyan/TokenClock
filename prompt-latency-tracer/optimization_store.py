"""Persist prompt optimization runs to disk."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from tracer import TRACE_DIR

OPT_FILE = TRACE_DIR / "optimizations.jsonl"


def save_optimization(
    *,
    original_prompt: str,
    optimized_prompt: str | None,
    metrics: dict,
    report: str,
) -> dict:
    record = {
        "id": uuid.uuid4().hex[:12],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "original_prompt": original_prompt,
        "optimized_prompt": optimized_prompt,
        "metrics": metrics,
        "report": report,
    }
    TRACE_DIR.mkdir(exist_ok=True)
    with open(OPT_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_optimizations() -> list[dict]:
    if not OPT_FILE.exists():
        return []
    rows = []
    with open(OPT_FILE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    rows.sort(key=lambda r: r.get("timestamp") or "")
    return rows


def clear_optimizations() -> int:
    count = len(load_optimizations())
    if OPT_FILE.exists():
        OPT_FILE.write_text("")
    return count
