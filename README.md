# TokenClock

Trace Gemini prompt latency end-to-end and optimize prompts for fewer tokens and lower latency — all locally.

Each LLM call is split into timed pipeline stages (prep → inference → post-process), stored in JSONL on disk, and shown in a React dashboard. A Gemini ADK agent can rewrite verbose prompts and verify savings with before/after measurements.

## Requirements

- Python 3.11+
- Node.js 18+ (dashboard build only)
- [Google AI Studio API key](https://aistudio.google.com/apikey)

## Quick start

### First time

```bash
cd prompt-latency-tracer
cp .env.example .env          # add your key(s) to .env — never commit this file
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cd ../dashboard && npm install && npm run build

cd ../prompt-latency-tracer && python server.py
```

Open **http://127.0.0.1:5001** (default port; avoids macOS AirPlay on 5000).

### Already set up

```bash
cd prompt-latency-tracer
source venv/bin/activate      # Windows: venv\Scripts\activate
python server.py
```

Rebuild the dashboard only after editing `dashboard/src/`:

```bash
cd dashboard && npm run build
```

Press `Ctrl+C` to stop the server. Trace data persists between sessions.

## Configuration

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Purpose |
|----------|----------|---------|
| `GOOGLE_API_KEY` | yes | Google AI Studio key (comma-separated for multiple) |
| `GOOGLE_API_KEY_2` | no | Fallback key; auto-rotates on 429 quota errors |
| `MODEL_NAME` | yes | e.g. `gemini-2.5-flash` |
| `PORT` | no | Web server port (default `5001`) |
| `OTEL_CONSOLE` | no | `1` to print spans to the terminal |

Free tier: `gemini-2.5-flash` is ~20 requests/day per key. The optimizer uses several calls per run.

## Dashboard

- **Traces** — run prompts, view latency/token charts, compare original vs optimized prompts. Role column: **compare** (optimization measurements) or **test** (manual/automatic runs). Delete one run with the trash icon, or clear all with **Clear run data**.
- **Optimizer** — paste a prompt, get a rewritten version with side-by-side metrics and history.

## CLI

From `prompt-latency-tracer/` with the venv active:

```bash
python main.py -p "Explain recursion briefly"   # single traced prompt
python main.py                                  # built-in benchmark prompts
python optimize.py "Your verbose prompt…"       # agent optimization report
python report.py                                # aggregated latency summary
```

## Data & APIs

Stored under `prompt-latency-tracer/traces/` (gitignored):

| File | Contents |
|------|----------|
| `spans.jsonl` | All Gemini trace runs |
| `optimizations.jsonl` | Optimizer session history |

| Action | Dashboard | API |
|--------|-----------|-----|
| Clear all traces | Traces → Clear run data | `POST /api/traces/clear` |
| Delete one trace | Traces → trash icon | `POST /api/traces/delete` `{ "traceId": "…" }` |
| Clear optimization history | Optimizer → Clear history | `POST /api/optimizations/clear` |

## Development

```bash
cd dashboard && npm run dev    # hot reload; run server.py separately for live API
```

## License

MIT — see [LICENSE](LICENSE).
