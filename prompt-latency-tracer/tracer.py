# tracer.py
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
