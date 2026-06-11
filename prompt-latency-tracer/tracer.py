# tracer.py
import os
from pathlib import Path

from dotenv import load_dotenv

from env_bootstrap import ensure_env
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource

ensure_env()
load_dotenv()

TRACE_DIR = Path(__file__).resolve().parent / "traces"
TRACE_FILE = TRACE_DIR / "spans.jsonl"


def setup_tracer():
    resource = Resource.create({
        "service.name": "tokenclock",
        "service.version": "1.0.0",
        "deployment.environment": "development",
    })

    provider = TracerProvider(resource=resource)

    TRACE_DIR.mkdir(exist_ok=True)
    trace_fh = open(TRACE_FILE, "a", encoding="utf-8")
    file_exporter = ConsoleSpanExporter(
        out=trace_fh,
        formatter=lambda span: span.to_json(indent=None) + "\n",
    )
    provider.add_span_processor(SimpleSpanProcessor(file_exporter))

    if os.getenv("OTEL_CONSOLE") == "1":
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    print(f"[tracer] Writing spans to {TRACE_FILE}")
    return trace.get_tracer("tokenclock.tracer"), provider
