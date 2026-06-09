# Prompt-to-Response Latency Tracer

Traces Gemini prompt latency end-to-end with OpenTelemetry — preparation,
inference, and post-processing as child spans. Traces are written to a local
JSONL file and explored through an interactive web dashboard (or a CLI report).

## What still needs to be added (and why)

The project runs fully today, but **one capability is missing and can't be added
without help: admin access to a Dynatrace environment.**

- **Goal:** stream traces to Dynatrace. That requires a *regular* API token with
  the **`openTelemetryTrace.ingest`** scope.
- **Why our credentials can't do it:**
  - The `dt0c01…` token is a **personal access token** with only
    `apiTokens.write`; Dynatrace does not allow ingest scopes on personal tokens,
    and a personal token can only create more personal tokens.
  - The `dt0s16…` platform token is missing `openpipeline:traces:ingest`.
  - Neither scope can be granted without an **admin account**, which we don't have.
- **What to add:** an admin needs to create a regular API token with
  `openTelemetryTrace.ingest` (or grant you admin on a tenant — e.g. your own
  free trial tenant, where you're automatically admin). See
  [Enabling Dynatrace](#enabling-dynatrace).
- **Until then:** the app is **local-first** — traces go to
  `traces/spans.jsonl` and are viewed in the dashboard/report. Dynatrace export
  is already wired and flag-gated (`DYNATRACE_ENABLED`), so it turns on with
  **zero code changes** once a valid token exists. Check current status anytime
  with `python check_dynatrace.py` or the Dynatrace badge in the UI.

Nothing else is required to run: API keys ship in the repo via
`env_bootstrap.py`, which writes `prompt-latency-tracer/.env` automatically on
first run.

## How to run

Prerequisites: Python 3.8+ and Node 18+. No manual key setup — the first
`python server.py` (or `main.py`) creates `.env` from bundled defaults.

```bash
# 1. Backend dependencies
cd prompt-latency-tracer
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Build the dashboard (one-time; also after any frontend change)
cd ../dashboard && npm install && npm run build

# 3. Launch the web app — opens http://127.0.0.1:5000 in your browser
cd ../prompt-latency-tracer && python server.py
```

In the browser you can **Run automatic test** (built-in prompts) or enter a
**self test** (your own prompt); results stream into the table live. The header
shows **Dynatrace** and **Google** health badges.

### CLI only (no web UI)

```bash
python main.py                 # built-in prompts; -i interactive / -p "single prompt"
python report.py               # aggregated latency report
python check_dynatrace.py      # Dynatrace readiness check
```

Both paths append spans to `traces/spans.jsonl`.

### How to end a session

**Web app (`python server.py`):** press `Ctrl+C` in the terminal where the server
is running. That stops the Flask process and closes the API; the browser tab can
stay open, but it will no longer receive live updates. Traces already written to
`traces/spans.jsonl` are kept.

**CLI (`python main.py`):** the process exits on its own when the prompt batch
finishes. In interactive mode (`-i`), type `quit` or press `Ctrl+C` to stop early.

**Optional cleanup:** if you activated the virtualenv, run `deactivate` when
you're done. You do not need to delete `traces/spans.jsonl` or rebuild the
dashboard between sessions.

## Configuration (`.env`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `GOOGLE_API_KEY` | yes | Google AI Studio key (comma-separated for multiple) |
| `GOOGLE_API_KEY_2` | no | Fallback key; used automatically when the first hits quota |
| `MODEL_NAME` | yes | e.g. `gemini-2.5-flash` |
| `OTEL_CONSOLE` | no | `1` to also pretty-print spans to the console |
| `DYNATRACE_ENABLED` | no | `1` to also export to Dynatrace OTLP (default `0`) |
| `DYNATRACE_ENDPOINT` | no | `https://{env-id}.live.dynatrace.com/api/v2/otlp` |
| `DYNATRACE_API_TOKEN` | no | Token for export and the readiness check |
| `DYNATRACE_AUTH_SCHEME` | no | `Api-Token` (classic) or `Bearer` (platform token) |

**Google free-tier limit:** `gemini-2.5-flash` is capped at ~20 requests/day per
key (plus a few/minute). On `429 RESOURCE_EXHAUSTED` the client auto-rotates to
`GOOGLE_API_KEY_2` if set, otherwise backs off; transient `503`s are retried.
Quota-exhausted runs are tracked but excluded from success-rate and latency
stats. Raise the ceiling by switching `MODEL_NAME` (e.g. `gemini-2.0-flash`) or
enabling billing.

## Enabling Dynatrace

### Path 1 — admin (gets traces into Dynatrace)
1. In Dynatrace → **Access Tokens** (not *Personal access tokens*), **Generate
   new token**; add the **`openTelemetryTrace.ingest`** scope. (No admin on this
   tenant? Spin up your own free trial tenant — you're its admin.)
2. In `.env`: set `DYNATRACE_ENABLED=1`, paste the token into
   `DYNATRACE_API_TOKEN`, keep `DYNATRACE_AUTH_SCHEME=Api-Token`, set
   `DYNATRACE_ENDPOINT`.
3. `python server.py` (or `main.py`) → spans go to both the local file and
   Dynatrace. The dashboard's Dynatrace badge flips to **Exporting** and the
   dashboard keeps reading the local file, so it shows the full run history
   whether or not export is on.

### Path 2 — diagnostics (works with the token we already have)
`python check_dynatrace.py` (also powering the dashboard badge) reports whether
ingest will work and what's missing. It first introspects the token via
`apiTokens/lookup`; if the token can't introspect itself (e.g. an admin token
scoped *only* for ingest, or a platform token), it falls back to probing the OTLP
ingest endpoint directly — so a valid admin key reads **healthy** either way.

## Dashboard & rebuilding

The React + Recharts dashboard (`dashboard/`) is served by `server.py` and shows
run controls, a runs table, per-run latency waterfall, aggregate charts, and live
health badges.

- **After changing anything in `dashboard/src`, rebuild** so the served app
  updates: `cd dashboard && npm run build`, then refresh the browser.
- For hot-reload development: `cd dashboard && npm run dev` (falls back to sample
  data when the API isn't reachable — run `server.py` alongside for live data).
- The header badge reads **LIVE** when connected to `server.py` and
  **SAMPLE DATA** when it can't reach the API (e.g. opened via the dev server or
  before the backend is running).

## Project layout

```
prompt-latency-tracer/
  server.py          # Flask app: serves dashboard + /api/run, /api/traces, /api/health
  tracer.py          # OTel tracer: local JSONL exporter (+ optional console / Dynatrace)
  llm_client.py      # Gemini call with traced pipeline spans + key failover
  usage.py           # Tracks Google daily request quota per key
  main.py            # CLI entry point + latency summary
  report.py          # Aggregated latency report from spans.jsonl
  check_dynatrace.py # Dynatrace token readiness check (CLI + API)
dashboard/           # React + Recharts web UI
```

## In-depth summary

This section explains the whole project end to end so it can be understood
without reading the code.

### What problem it solves
When you send a prompt to an LLM, "it felt slow" isn't actionable. This tool
breaks each request into measurable stages and records exactly where the time and
tokens go, then makes that history browsable. It's a small, self-contained
example of **observability for LLM calls** using OpenTelemetry — the same tracing
standard used in production systems — without needing a paid backend to be useful.

### The three-stage pipeline
Every prompt is executed as one **trace** made of nested **spans** (timed
operations). The root span `llm.full_pipeline` wraps three children:

1. **`llm.prompt_preparation`** — building the request before the network call
   (negligible time, included for completeness).
2. **`llm.inference`** — the actual Gemini API call. This dominates latency and
   is where token counts (prompt / completion / total) are recorded.
3. **`llm.post_processing`** — handling the response after it returns.

Each span carries attributes (model name, prompt text, durations, token counts,
success flag) and, on failure, an `exception` event with the error message. This
parent/child structure is what lets the UI draw a per-run "waterfall."

### How data flows
```
prompt → llm_client (creates spans) → tracer (OTel provider)
                                         ├─ always → traces/spans.jsonl  (one JSON span per line)
                                         ├─ optional → console            (OTEL_CONSOLE=1)
                                         └─ optional → Dynatrace OTLP      (DYNATRACE_ENABLED=1 + valid token)
spans.jsonl → server.py (parses lines into runs) → /api/* → dashboard
spans.jsonl → report.py (CLI aggregate)
```
The local JSONL file is the **single source of truth**. Every other view (web
dashboard, CLI report, and even Dynatrace when enabled) is built from the same
spans, so they never disagree.

### Components
- **`llm_client.py`** — wraps the Gemini call in the three spans and returns a
  latency/token breakdown. Handles real-world API failure: exponential-backoff
  retries on transient `503`s, and automatic rotation to a second API key on
  `429` quota errors.
- **`tracer.py`** — configures the OpenTelemetry provider and decides where spans
  go. The local-file exporter is always on; console and Dynatrace are opt-in. The
  Dynatrace path is fully wired and flag-gated, so it activates with no code
  changes once a valid token exists.
- **`usage.py`** — persists per-key Google request counts to `usage.json` so the
  app can warn when a key is near its free-tier daily limit and mark keys as
  exhausted.
- **`server.py`** — a small Flask app that serves the built dashboard and exposes
  `/api/traces` (parsed run history), `/api/health` (Dynatrace + Google status),
  and `/api/run` (trigger a built-in or custom prompt). A lock prevents
  overlapping runs.
- **`check_dynatrace.py`** — answers "would trace ingest actually work?" It
  introspects the token's scopes, and if that's not possible, probes the ingest
  endpoint directly. Used by both the CLI and the dashboard's health badge.
- **`dashboard/`** — a React + Recharts single page: run controls, a sortable
  runs table with expandable per-run detail, a latency-over-time line chart, a
  token bar chart, and live Dynatrace/Google badges. It polls the API for live
  updates and falls back to bundled sample data when no backend is reachable.

### Key design decisions
- **Local-first, not Dynatrace-first.** Dynatrace trace ingest requires an admin
  -created token scope we can't grant on the available credentials, so the
  primary backend is a local file. This keeps the project fully runnable today
  while leaving Dynatrace as a one-flag upgrade.
- **Resilient by default.** Free-tier LLM APIs fail often; retries, key rotation,
  and per-run error capture mean one bad call never aborts a session, and
  quota-failed runs are visibly separated from genuine performance data.
- **One source of truth.** Centralizing on `spans.jsonl` keeps the CLI, web UI,
  and Dynatrace consistent and makes the data trivial to inspect or replay.
- **Honest health signals.** The dashboard reports the real state of external
  dependencies (Dynatrace readiness, Google quota) instead of hiding them, so
  it's clear when results are limited by infrastructure rather than the code.
