# report.py
"""
Aggregate OpenTelemetry spans from traces/spans.jsonl into a latency report.

Usage:
    python report.py
    python report.py --file traces/spans.jsonl
"""
import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parent / "traces" / "spans.jsonl"


def load_spans(path: Path):
    spans = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                spans.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return spans


def _parse_ts(ts: str) -> float:
    """Parse an ISO-8601 span timestamp (…Z) into epoch seconds."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def _duration_ms(span) -> float:
    """Prefer the recorded stage/inference attribute; else derive from timestamps."""
    attrs = span.get("attributes", {}) or {}
    for key in ("inference.duration_ms", "stage.duration_ms"):
        if key in attrs:
            return float(attrs[key])
    start, end = span.get("start_time"), span.get("end_time")
    if start and end:
        try:
            return round((_parse_ts(end) - _parse_ts(start)) * 1000, 2)
        except ValueError:
            pass
    return 0.0


def _percentile(values, pct):
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main():
    parser = argparse.ArgumentParser(description="Local latency report from spans.jsonl")
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    args = parser.parse_args()

    if not args.file.exists():
        print(f"No trace file at {args.file}. Run 'python main.py' first.")
        return

    spans = load_spans(args.file)
    if not spans:
        print("No spans found yet. Run 'python main.py' to generate some.")
        return

    by_name = defaultdict(list)
    for s in spans:
        by_name[s.get("name", "unknown")].append(_duration_ms(s))

    traces = {s.get("context", {}).get("trace_id") for s in spans}

    print(f"{'═' * 72}")
    print(f"Local latency report  ({args.file})")
    print(f"{'═' * 72}")
    print(f"Spans: {len(spans)}    Traces (prompts): {len(traces)}\n")

    print(f"{'span':<26}{'count':>7}{'avg ms':>10}{'p50':>10}{'p95':>10}")
    print(f"{'-' * 72}")
    for name in sorted(by_name):
        vals = [v for v in by_name[name] if v > 0]
        count = len(by_name[name])
        avg = sum(vals) / len(vals) if vals else 0.0
        print(f"{name:<26}{count:>7}{avg:>10.1f}{_percentile(vals, 50):>10.1f}{_percentile(vals, 95):>10.1f}")


if __name__ == "__main__":
    main()
