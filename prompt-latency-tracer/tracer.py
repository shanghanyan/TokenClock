# tracer.py
import os
from pathlib import Path
from dotenv import load_dotenv

from env_bootstrap import ensure_env
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.sdk.resources import Resource

ensure_env()
load_dotenv()

# Where local trace output is written (one JSON object per line, JSONL).
TRACE_DIR = Path(__file__).resolve().parent / "traces"
TRACE_FILE = TRACE_DIR / "spans.jsonl"


def _traces_url(endpoint: str) -> str:
    """Accept either the OTLP base (…/api/v2/otlp) or a full …/v1/traces URL."""
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/v1/traces"):
        return endpoint
    return f"{endpoint}/v1/traces"


def _add_dynatrace_exporter(provider: TracerProvider) -> bool:
    """
    Optional. Only used when DYNATRACE_ENABLED=1 AND a token/endpoint are set.
    Off by default because trace ingest requires the openTelemetryTrace.ingest
    scope, which is not available on the tokens we have.
    """
    if os.getenv("DYNATRACE_ENABLED") != "1":
        return False
    endpoint = os.getenv("DYNATRACE_ENDPOINT")
    token = os.getenv("DYNATRACE_API_TOKEN")
    if not (endpoint and token):
        return False

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    scheme = os.getenv("DYNATRACE_AUTH_SCHEME", "Api-Token")
    if scheme.lower() == "bearer":
        headers = {"Authorization": f"Bearer {token}"}
    else:
        headers = {"Authorization": f"Api-Token {token}"}

    exporter = OTLPSpanExporter(endpoint=_traces_url(endpoint), headers=headers)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return True


def setup_tracer():
    resource = Resource.create({
        "service.name": "prompt-latency-tracer",
        "service.version": "1.0.0",
        "deployment.environment": "development"
    })

    provider = TracerProvider(resource=resource)

    # --- Primary backend: local JSONL file (always on) ---
    TRACE_DIR.mkdir(exist_ok=True)
    trace_fh = open(TRACE_FILE, "a", encoding="utf-8")
    file_exporter = ConsoleSpanExporter(
        out=trace_fh,
        formatter=lambda span: span.to_json(indent=None) + "\n",
    )
    provider.add_span_processor(SimpleSpanProcessor(file_exporter))

    # --- Optional: pretty spans to stdout (OTEL_CONSOLE=1) ---
    if os.getenv("OTEL_CONSOLE") == "1":
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    # --- Optional: Dynatrace OTLP (off unless DYNATRACE_ENABLED=1) ---
    dt_on = _add_dynatrace_exporter(provider)

    trace.set_tracer_provider(provider)

    print(f"[tracer] Local traces  -> {TRACE_FILE}")
    print(f"[tracer] Dynatrace OTLP -> {'enabled' if dt_on else 'disabled'}")

    return trace.get_tracer("prompt.tracer"), provider
