# Prompt-to-Response Latency Tracer

Traces LLM prompt latency end-to-end with OpenTelemetry and exports spans to Dynatrace. Each run records preparation, inference, and post-processing as child spans.

## Prerequisites

- Python 3.8+
- Dynatrace environment (SaaS or Managed)
- OpenAI API key

## Setup

```bash
cd prompt-latency-tracer
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env` and set your values:

| Variable | Source |
|----------|--------|
| `DYNATRACE_ENDPOINT` | Settings → Ingest APIs → OTLP |
| `DYNATRACE_API_TOKEN` | Access Tokens → `openTelemetryTrace.ingest` |
| `OPENAI_API_KEY` | OpenAI dashboard |
| `MODEL_NAME` | e.g. `gpt-4o` |

## Run

Activate the venv first (`source venv/bin/activate`).

**Built-in test prompts (default):**

```bash
python main.py
```

**Interactive mode:**

```bash
python main.py --interactive
# or: python main.py -i
```

Type `exit` or `quit` to stop.

**Single prompt:**

```bash
python main.py --prompt "Summarise the plot of Hamlet in two sentences."
# or: python main.py -p "What causes a stack overflow?"
```

Spans are flushed to Dynatrace on exit (including Ctrl+C in interactive mode).

## View traces in Dynatrace

1. **Distributed Traces** → search for service `prompt-latency-tracer`
2. Each run is a trace: `llm.prompt_preparation` → `llm.inference` → `llm.post_processing`
3. Span attributes include `inference.duration_ms`, token counts, and prompt/response lengths

## Project layout

```
tracer.py      # OTel tracer + Dynatrace OTLP export
llm_client.py  # OpenAI call with traced pipeline spans
main.py        # CLI entry point
```
