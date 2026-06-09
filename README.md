# Prompt-to-Response Latency Tracer

Traces LLM prompt latency end-to-end with OpenTelemetry. Each run records
preparation, inference, and post-processing as child spans.

By default, traces are exported to a **local JSONL file** (`traces/spans.jsonl`)
and summarized with a built-in report — no external observability backend or
admin token required. Dynatrace OTLP export is available as an optional add-on
if you ever obtain a token with the `openTelemetryTrace.ingest` scope.

## Prerequisites

- Python 3.8+
- Google AI Studio API key (for the LLM)

## Setup

```bash
cd prompt-latency-tracer
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Set your values in `.env`:

| Variable | Required | Purpose |
|----------|----------|---------|
| `GOOGLE_API_KEY` | yes | Google AI Studio (aistudio.google.com) |
| `MODEL_NAME` | yes | e.g. `gemini-2.5-flash` |
| `OTEL_CONSOLE` | no | `1` to also pretty-print spans to the console |
| `DYNATRACE_ENABLED` | no | `1` to also export to Dynatrace OTLP (default `0`) |
| `DYNATRACE_ENDPOINT` | no | `https://{env-id}.live.dynatrace.com/api/v2/otlp` |
| `DYNATRACE_API_TOKEN` | no | **Regular** API token with `openTelemetryTrace.ingest` |
| `DYNATRACE_AUTH_SCHEME` | no | `Api-Token` (classic) or `Bearer` (platform token) |

## Run

Activate the venv first (`source venv/bin/activate`).

**Built-in test prompts (default):**

```bash
python main.py
```

**Interactive mode:**

```bash
python main.py --interactive   # or -i
```

Type `exit` or `quit` to stop.

**Single prompt:**

```bash
python main.py --prompt "Summarise the plot of Hamlet in two sentences."
# or: python main.py -p "What causes a stack overflow?"
```

Each run prints a per-prompt latency line and an end-of-run summary table, and
appends spans to `traces/spans.jsonl`.

## View traces (local)

```bash
python report.py
```

This aggregates `traces/spans.jsonl` into per-span counts and avg/p50/p95
latencies — the local stand-in for a Dynatrace trace view.

## Optional: export to Dynatrace

Trace ingest needs a **non-personal** API token with the
`openTelemetryTrace.ingest` scope (personal access tokens cannot hold ingest
scopes). Once you have one:

1. Set `DYNATRACE_ENABLED=1`, `DYNATRACE_API_TOKEN=...`, and `DYNATRACE_ENDPOINT`.
2. Run `python main.py`. Spans go to both the local file and Dynatrace.

## Project layout

```
tracer.py      # OTel tracer: local JSONL exporter (+ optional console / Dynatrace)
llm_client.py  # Gemini call with traced pipeline spans
main.py        # CLI entry point + latency summary
report.py      # Aggregated latency report from spans.jsonl
```
