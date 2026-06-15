# TokenClock

Trace Gemini prompt latency end-to-end and **optimize prompts for fewer tokens and lower latency** — all locally, with no external observability backend.

TokenClock breaks every LLM call into timed pipeline stages, stores traces on disk, and includes a Gemini-powered agent that rewrites verbose prompts while measuring before/after savings.

## What it does

1. **Trace** — Each prompt runs through three OpenTelemetry spans: preparation → inference → post-processing. Token counts and millisecond timings are recorded for each stage.
2. **Visualize** — A React dashboard shows run history, per-stage waterfalls, latency-over-time charts, and token usage.
3. **Optimize** — An ADK agent reads your local trace history, runs baseline and verification Gemini calls, and returns a rewritten prompt with a metrics comparison.

Everything persists to `prompt-latency-tracer/traces/spans.jsonl`. No cloud tracing service required.

## Requirements

- **Python 3.11+**
- **Node.js 18+** (dashboard build only)
- **Google AI Studio API key** — [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

## Setup

1. `cd prompt-latency-tracer && cp .env.example .env`
2. Fill in your API keys in `.env` (get them from [Google AI Studio](https://aistudio.google.com/apikey))
3. Never commit `.env` — it is gitignored

When you rotate keys, update `.env` only.

## Quick start

```bash
# Backend
cd prompt-latency-tracer
cp .env.example .env   # then edit .env with your keys
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Dashboard (one-time, or after frontend changes)
cd ../dashboard && npm install && npm run build

# Launch
cd ../prompt-latency-tracer && python server.py
```

Opens http://127.0.0.1:5000 in your browser.

### CLI

```bash
python main.py                              # run built-in benchmark prompts
python main.py -p "Explain recursion briefly"   # single prompt
python main.py -i                           # interactive REPL
python optimize.py "Your verbose prompt…"   # agent optimization report
python report.py                            # aggregated latency summary
```

Press `Ctrl+C` to stop the web server. Traces in `traces/spans.jsonl` are kept between sessions.

## Configuration (`.env`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `GOOGLE_API_KEY` | yes | Google AI Studio key (comma-separated for multiple) |
| `GOOGLE_API_KEY_2` | no | Fallback key; auto-rotates on 429 quota errors |
| `MODEL_NAME` | yes | e.g. `gemini-2.5-flash` |
| `OTEL_CONSOLE` | no | `1` to also print spans to the terminal |
| `PORT` | no | Web server port (default `5000`) |

**Free-tier note:** `gemini-2.5-flash` is capped at ~20 requests/day per key. The optimizer uses 2+ calls per run, so budget accordingly. On `429 RESOURCE_EXHAUSTED` the client rotates to `GOOGLE_API_KEY_2` if set.

**Security:** Keep keys in `.env` only. If keys were ever committed (including in old `env_bootstrap.py` blobs), revoke them in Google AI Studio and generate new ones — deleting files does not remove them from git history.

## How tracing works

Every prompt creates one trace with nested spans:

```
llm.full_pipeline
├── llm.prompt_preparation   (negligible — request setup)
├── llm.inference            (Gemini API call — dominates latency + tokens)
└── llm.post_processing      (response handling)
```

```
prompt → llm_client (spans) → tracer → traces/spans.jsonl
                                      → server.py /api/traces → dashboard
                                      → report.py (CLI summary)
                                      → get_trace_history (agent tool)
```

## Prompt optimizer agent

The agent (`tokenclock_agent/`) uses [Google ADK](https://google.github.io/adk-docs/) with two tools:

| Tool | What it does |
|------|--------------|
| `get_trace_history` | Reads recent runs from `spans.jsonl` with aggregate stats |
| `measure_prompt` | Sends a prompt to Gemini and returns latency + token breakdown |

Typical flow: read history → measure baseline → analyze → rewrite → measure optimized → report savings.

### Using it in the dashboard

1. Start the app (`python server.py`) and open the dashboard.
2. Click **Optimizer** in the top navigation (or `#/optimizer`).
3. Paste a verbose prompt and click **Optimize prompt**.
4. Each run appears in **Optimization history** with:
   - **Original** vs **Optimized** side by side (char/word counts)
   - Before/after metrics (tokens, latency, inference)
   - Expandable full agent report
5. From **Traces**, use **Open in optimizer →** on any self-test prompt.

### Using it from the CLI

```bash
python optimize.py "Write a comprehensive detailed guide to Python async with many examples"
```

Output is the same structured report printed to the terminal. New traces from the agent runs append to `traces/spans.jsonl`.

### Clearing data

| What | Dashboard | API |
|------|-----------|-----|
| Trace runs | **Traces** → Clear run data | `POST /api/traces/clear` |
| Optimization history | **Optimizer** → Clear history | `POST /api/optimizations/clear` |

## Project layout

```
TokenClock/
  LICENSE
  README.md
  dashboard/                 # React + Recharts UI
  prompt-latency-tracer/
    optimization_store.py  # optimizations.jsonl persistence
    server.py                # Flask: traces + optimizer APIs
    main.py                  # CLI tracing entry point
    optimize.py              # CLI agent entry point
    llm_client.py            # Gemini client with traced pipeline
    tracer.py                # OpenTelemetry → local JSONL
    report.py                # CLI aggregate report
    usage.py                 # Per-key daily quota tracking
    tokenclock_agent/
      agent.py               # ADK LlmAgent definition
      runner.py              # ADK Runner wrapper
      tools.py               # measure_prompt + get_trace_history
      report_parser.py       # Parse report + measurement summaries
      trace_reader.py        # spans.jsonl parser
    traces/spans.jsonl       # trace output (created at runtime)
```

## Development

Rebuild the dashboard after editing `dashboard/src/`:

```bash
cd dashboard && npm run build
```

For hot-reload UI development:

```bash
cd dashboard && npm run dev    # Vite dev server; falls back to sample data without backend
```

Run the backend alongside for live data: `python server.py`.

## License

MIT — see [LICENSE](LICENSE).
