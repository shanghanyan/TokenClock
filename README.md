# TokenClock

An AI agent that **analyzes and rewrites prompts to use fewer tokens and less latency**
while preserving meaning — built for the [Google Cloud Rapid Agent Hackathon](https://rapid-agent.devpost.com/) (Dynatrace track).

**Runtime stack (all invoked, not README-only):**

| Component | How it's used |
|-----------|---------------|
| **Gemini** | ADK `LlmAgent` + `measure_prompt` tool call `google-genai` |
| **Google Cloud Agent Builder (ADK)** | `google-adk` — `LlmAgent`, `Runner`, `FunctionTool`, `McpToolset` |
| **Dynatrace MCP** | `McpToolset` → local stub (default) or live `@dynatrace-oss/dynatrace-mcp-server` / hosted MCP URL |

Every prompt run is traced with OpenTelemetry to `traces/spans.jsonl` and shown in a React dashboard.

## Dynatrace in this project (two different APIs)

The repo already talks to Dynatrace, but **OTLP trace export ≠ MCP**. Same tenant, different endpoints and token scopes:

| Feature | File | Endpoint | Token / scopes |
|---------|------|----------|----------------|
| **MCP (hackathon requirement)** | `tokenclock_agent/agent.py` | `*.apps.dynatrace.com/.../dynatrace-mcp/mcp` | **Platform Token** (Bearer): `mcp-gateway:servers:invoke`, `mcp-gateway:servers:read`, … |
| **OTLP trace export (optional)** | `tracer.py`, `check_dynatrace.py` | `*.live.dynatrace.com/api/v2/otlp` | Platform or API token: `openTelemetryTrace.ingest` |

Your bundled `DYNATRACE_API_TOKEN` can be reused for MCP **only if** it is a Platform Token with MCP gateway scopes. The existing personal/classic tokens lack both ingest and MCP scopes. The agent already tries `DT_PLATFORM_TOKEN` then falls back to `DYNATRACE_API_TOKEN`.

**Readiness checks:**
```bash
python check_dynatrace_mcp.py   # agent MCP tools (required for live MCP)
python check_dynatrace.py       # optional OTLP export
```

## Accounts you need

### 1. Google AI Studio (required — you likely have this)

- **Sign up:** [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- **What for:** Gemini inference via ADK (`GOOGLE_API_KEY`)
- **Cost:** Free tier (~20 req/day per key on `gemini-2.5-flash`); add `GOOGLE_API_KEY_2` for failover
- **Agent Builder:** ADK runs locally with an AI Studio key — no GCP billing account required for the hackathon demo. Optional: a Google Cloud project + Vertex AI if you want hosted deployment later.

### 2. Dynatrace free trial (required for live MCP + optional trace export)

- **Sign up:** [dynatrace.com/signup](https://www.dynatrace.com/signup/) — you are **admin** on your own trial tenant
- **What for:** Dynatrace MCP tools (`execute_dql`, `generate_dql_from_natural_language`, …) that the agent calls at runtime

**Create a Platform Token** (Account Management → Identity & access management → OAuth clients → **Platform tokens**):

| Scope | Why |
|-------|-----|
| `mcp-gateway:servers:invoke` | Invoke MCP tools |
| `mcp-gateway:servers:read` | Discover MCP tools |
| `davis-copilot:nl2dql:execute` | `generate_dql_from_natural_language` |
| `storage:buckets:read` | `execute_dql` |

Optional (OTLP trace export to Dynatrace UI):

| Scope | Why |
|-------|-----|
| `openTelemetryTrace.ingest` | Export OTel spans from `tracer.py` |

**Configure in `.env`:**

```bash
DYNATRACE_MCP_STUB=0
DYNATRACE_MCP_URL=https://YOUR_ENV_ID.apps.dynatrace.com/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp
DT_PLATFORM_TOKEN=dt0c01.XXXX   # or DYNATRACE_API_TOKEN
```

Alternative (OSS MCP server via npx + Node 18+):

```bash
DYNATRACE_MCP_STUB=0
DT_ENVIRONMENT_URL=https://YOUR_ENV_ID.live.dynatrace.com
DT_PLATFORM_TOKEN=dt0c01.XXXX
```

**Without a Dynatrace tenant:** leave `DYNATRACE_MCP_STUB=1` (default). The agent uses a local MCP stub that reads your `spans.jsonl` — enough to demo the full ADK + MCP loop locally.

### 3. Node.js 18+ (required for live Dynatrace OSS MCP)

Only if using `DYNATRACE_MCP_STUB=0` with the npx server path. Not needed for the hosted MCP URL or the local stub.

---

## How to run

Prerequisites: **Python 3.11+**, Node 18+ (dashboard build; Dynatrace OSS MCP optional).

```bash
cd prompt-latency-tracer
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cd ../dashboard && npm install && npm run build

cd ../prompt-latency-tracer && python server.py
```

Open http://127.0.0.1:5000 — use **Optimize with agent** or the trace/run controls.

### CLI

```bash
python optimize.py "Write a very detailed essay about async Python with many examples"
python main.py                 # benchmark prompts (tracing only)
python check_dynatrace_mcp.py  # MCP readiness (agent)
python check_dynatrace.py      # OTLP ingest readiness (optional)
```

## Submission path (your understanding is correct)

1. **MCP first** — Sign up for a [Dynatrace free trial](https://www.dynatrace.com/signup/), create a Platform Token with MCP scopes, set `DYNATRACE_MCP_STUB=0`, run `python check_dynatrace_mcp.py` until it says **ready**. Until then, stub mode runs the full agent locally for development.
2. **Run locally** — `python server.py` + dashboard; demo optimize flow with live MCP.
3. **Deploy** — Host `server.py` somewhere public (e.g. Google Cloud Run free tier, Render, Railway). Needs a cloud account for the **hosted URL** Devpost requires; Google AI Studio key still powers Gemini.
4. **Ship** — Public GitHub repo with an **open-source license** (Apache-2.0/MIT in repo root), ~3 min demo video, Devpost form, select **Dynatrace** track.

OTLP export to Dynatrace is optional polish, not required for the hackathon MCP integration.

## Agent workflow

```
User prompt
    → ADK LlmAgent (Gemini)
        ├─ measure_prompt (baseline traced Gemini call)
        ├─ Dynatrace MCP: generate_dql → execute_dql (historical patterns)
        ├─ Gemini reasoning → rewritten prompt
        └─ measure_prompt (verify token/latency savings)
    → structured report in dashboard / API
    → spans → traces/spans.jsonl (+ optional Dynatrace OTLP)
```

## Configuration (`.env`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `GOOGLE_API_KEY` | yes | Gemini via ADK |
| `MODEL_NAME` | yes | e.g. `gemini-2.5-flash` |
| `DYNATRACE_MCP_STUB` | no | `1` = local MCP stub (default); `0` = live Dynatrace |
| `DYNATRACE_MCP_URL` | for live MCP | Hosted Dynatrace MCP endpoint |
| `DT_PLATFORM_TOKEN` | for live MCP | Platform token with MCP scopes |
| `DT_ENVIRONMENT_URL` | alt live MCP | For npx `@dynatrace-oss/dynatrace-mcp-server` |
| `DYNATRACE_ENABLED` | no | `1` to also OTLP-export traces |
| `DYNATRACE_ENDPOINT` | no | `https://{env}.live.dynatrace.com/api/v2/otlp` |
| `DYNATRACE_API_TOKEN` | no | Token with `openTelemetryTrace.ingest` |

## Project layout

```
prompt-latency-tracer/
  tokenclock_agent/
    agent.py           # ADK LlmAgent + McpToolset (Dynatrace) + measure_prompt
    runner.py          # ADK Runner (Flask / CLI entry)
    tools.py           # FunctionTool: traced Gemini measurement
    mcp_stub.py        # Local Dynatrace MCP stub (reads spans.jsonl)
    trace_reader.py    # Parse spans.jsonl for MCP + dashboard
  server.py            # Flask: /api/optimize, /api/run, /api/traces
  optimize.py          # CLI agent entry
  llm_client.py        # Gemini calls (used by measure_prompt)
  tracer.py            # OTel → JSONL + optional Dynatrace OTLP
dashboard/             # React UI with agent optimize panel
```

## Hackathon submission checklist

- Hosted project URL: deploy `server.py` (e.g. Cloud Run) or document local demo
- Public repo with OSS license
- ~3 min demo video showing: agent optimize flow, ADK + MCP tool calls, trace dashboard
- Track: **Dynatrace**
