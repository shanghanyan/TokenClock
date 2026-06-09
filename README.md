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

Nothing else is required to run: the Google AI Studio key (already in `.env`)
covers the LLM.

## How to run

Prerequisites: Python 3.8+, Node 18+, and a Google AI Studio key in `.env`.

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
3. `python server.py` (or `main.py`) → spans go to both the local file and Dynatrace.

### Path 2 — diagnostics (works with the token we already have)
`python check_dynatrace.py` uses the token's `apiTokens.write` capability to look
up its own scopes and report whether ingest is possible and what's missing.

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
