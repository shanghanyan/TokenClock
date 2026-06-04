# tracer.py
import os
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

load_dotenv()


def setup_tracer():
    resource = Resource.create({
        "service.name": "prompt-latency-tracer",
        "service.version": "1.0.0",
        "deployment.environment": "development"
    })

    exporter = OTLPSpanExporter(
        endpoint=f"{os.getenv('DYNATRACE_ENDPOINT')}/v1/traces",
        headers={
            "Authorization": f"Api-Token {os.getenv('DYNATRACE_API_TOKEN')}"
        }
    )

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    return trace.get_tracer("prompt.tracer"), provider
