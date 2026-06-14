"""Parse agent optimization reports into structured fields."""

from __future__ import annotations

import re
from typing import Any


def parse_optimized_prompt(report: str) -> str | None:
    """Extract the rewritten prompt from the agent's markdown report."""
    if not report:
        return None

    m = re.search(
        r"#{1,3}\s*Optimized prompt\b[^\n]*(?:\s*\n+|\s+)(.*?)(?=\n#{1,3}\s+\S|\Z)",
        report,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return None

    body = m.group(1).strip()
    body = re.sub(r"^\*\*|\*\*$", "", body).strip()

    fenced = re.match(r"^```(?:\w*\n)?(.+?)```\s*$", body, re.DOTALL)
    if fenced:
        body = fenced.group(1).strip()

    # Drop stray markdown list items if the model leaked into this section.
    lines = []
    for line in body.splitlines():
        if re.match(r"^#{1,3}\s", line):
            break
        if re.match(r"^[-*]\s", line) and lines:
            break
        lines.append(line)
    body = "\n".join(lines).strip().strip('"\'')
    return body or None


def resolve_optimized_prompt(report: str, metrics: dict[str, Any] | None) -> str | None:
    """Parsed report text, else the prompt from the verification measure_prompt call."""
    parsed = parse_optimized_prompt(report)
    if parsed:
        return parsed
    opt = (metrics or {}).get("optimized") or {}
    prompt = opt.get("prompt")
    return prompt.strip() if isinstance(prompt, str) and prompt.strip() else None


def summarize_measurements(measurements: list[dict[str, Any]]) -> dict[str, Any]:
    """Pair first/last successful measure_prompt results as baseline vs optimized."""
    ok = [m for m in measurements if m.get("success")]
    if not ok:
        return {"baseline": None, "optimized": None, "savings": None}
    baseline = ok[0]
    optimized = ok[-1] if len(ok) > 1 else None
    savings = None
    if optimized and optimized is not baseline:
        bt, ot = baseline.get("tokens") or 0, optimized.get("tokens") or 0
        bm, om = baseline.get("total_ms") or 0, optimized.get("total_ms") or 0
        bi, oi = baseline.get("inference_ms") or 0, optimized.get("inference_ms") or 0
        savings = {
            "tokens": bt - ot,
            "tokens_pct": round(100 * (bt - ot) / bt, 1) if bt else 0,
            "total_ms": round(bm - om, 2),
            "total_ms_pct": round(100 * (bm - om) / bm, 1) if bm else 0,
            "inference_ms": round(bi - oi, 2),
        }
    return {"baseline": baseline, "optimized": optimized, "savings": savings}
