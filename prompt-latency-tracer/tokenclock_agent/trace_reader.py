"""Read OpenTelemetry spans from the local JSONL trace file."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from tracer import TRACE_FILE


def _trace_id(span: dict) -> str | None:
    return (span.get("context") or {}).get("trace_id") or span.get("trace_id")


def _ms(start: str | None, end: str | None) -> float:
    if not start or not end:
        return 0.0
    try:
        s = datetime.fromisoformat(start.replace("Z", "+00:00"))
        e = datetime.fromisoformat(end.replace("Z", "+00:00"))
        return round((e - s).total_seconds() * 1000, 2)
    except (AttributeError, ValueError):
        return 0.0


def load_runs(path: Path | None = None) -> list[dict]:
    """Parse spans.jsonl into one dict per llm.full_pipeline run."""
    path = path or TRACE_FILE
    if not path.exists():
        return []

    by_trace: dict[str, list[dict]] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                span = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = _trace_id(span)
            if tid:
                by_trace.setdefault(tid, []).append(span)

    runs = []
    for spans in by_trace.values():
        root = next((s for s in spans if s.get("name") == "llm.full_pipeline"), None)
        if not root:
            continue
        inf = next((s for s in spans if s.get("name") == "llm.inference"), None)
        ra = root.get("attributes") or {}
        ia = (inf or {}).get("attributes") or {}
        runs.append({
            "trace_id": _trace_id(root),
            "timestamp": root.get("start_time"),
            "prompt": ra.get("prompt.text", ""),
            "model": ra.get("model.name", ""),
            "total_ms": _ms(root.get("start_time"), root.get("end_time")),
            "inference_ms": ia.get("inference.duration_ms", 0),
            "prompt_tokens": ia.get("tokens.prompt", 0),
            "completion_tokens": ia.get("tokens.completion", 0),
            "total_tokens": ia.get("tokens.total") or ra.get("pipeline.total_tokens") or 0,
            "success": ra.get("pipeline.success") is not False,
        })
    runs.sort(key=lambda r: r.get("timestamp") or "")
    return runs


def summarize_runs(runs: list[dict]) -> dict:
    ok = [r for r in runs if r["success"] and r["total_tokens"]]
    if not ok:
        return {"count": len(runs), "successful": 0}
    lats = [r["total_ms"] for r in ok]
    tokens = [r["total_tokens"] for r in ok]
    return {
        "count": len(runs),
        "successful": len(ok),
        "avg_total_ms": round(sum(lats) / len(lats), 2),
        "p95_total_ms": round(sorted(lats)[int(0.95 * (len(lats) - 1))], 2),
        "avg_total_tokens": round(sum(tokens) / len(tokens), 1),
        "max_total_tokens": max(tokens),
        "min_total_tokens": min(tokens),
    }
