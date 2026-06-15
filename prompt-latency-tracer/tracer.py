import json
import os
from pathlib import Path

import env  # noqa: F401 — loads .env
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource

TRACE_DIR = Path(__file__).resolve().parent / "traces"
TRACE_FILE = TRACE_DIR / "spans.jsonl"
_trace_fh = None


def setup_tracer():
    global _trace_fh
    resource = Resource.create({
        "service.name": "tokenclock",
        "service.version": "1.0.0",
        "deployment.environment": "development",
    })

    provider = TracerProvider(resource=resource)

    TRACE_DIR.mkdir(exist_ok=True)
    _trace_fh = open(TRACE_FILE, "a", encoding="utf-8")
    file_exporter = ConsoleSpanExporter(
        out=_trace_fh,
        formatter=lambda span: span.to_json(indent=None) + "\n",
    )
    provider.add_span_processor(SimpleSpanProcessor(file_exporter))

    if os.getenv("OTEL_CONSOLE") == "1":
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    print(f"[tracer] Writing spans to {TRACE_FILE}")
    return trace.get_tracer("tokenclock.tracer"), provider


def clear_traces() -> int:
    """Delete all stored spans. Returns the number of runs removed."""
    from tokenclock_agent.trace_reader import load_runs

    count = len(load_runs())
    global _trace_fh
    if _trace_fh is not None:
        _trace_fh.seek(0)
        _trace_fh.truncate(0)
        _trace_fh.flush()
    elif TRACE_FILE.exists():
        TRACE_FILE.write_text("")
    return count


def _trace_id(span: dict) -> str | None:
    return (span.get("context") or {}).get("trace_id") or span.get("trace_id")


def _reopen_trace_file() -> None:
    global _trace_fh
    if _trace_fh is not None:
        _trace_fh.close()
    TRACE_DIR.mkdir(exist_ok=True)
    _trace_fh = open(TRACE_FILE, "a", encoding="utf-8")


def delete_trace(trace_id: str) -> bool:
    """Remove all spans for one trace. Returns True if any spans were removed."""
    if not trace_id or not TRACE_FILE.exists():
        return False

    kept: list[str] = []
    removed = False
    with open(TRACE_FILE, encoding="utf-8") as fh:
        for line in fh:
            raw = line.rstrip("\n")
            if not raw.strip():
                continue
            try:
                span = json.loads(raw)
            except json.JSONDecodeError:
                kept.append(raw)
                continue
            if _trace_id(span) == trace_id:
                removed = True
                continue
            kept.append(raw)

    if not removed:
        return False

    global _trace_fh
    if _trace_fh is not None:
        _trace_fh.close()
        _trace_fh = None
    TRACE_FILE.write_text("\n".join(kept) + ("\n" if kept else ""))
    _reopen_trace_file()
    return True
