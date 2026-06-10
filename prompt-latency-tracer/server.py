# server.py
"""
Launches the Prompt Latency Tracer web app: serves the React dashboard and a
small API to run tests, read traces, and report system health.

    python server.py     # starts http://127.0.0.1:5000 and opens the browser
"""
import json
import os
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

import usage
import llm_client
from check_dynatrace import check_readiness
from check_dynatrace_mcp import check_mcp_readiness
from llm_client import run_traced_prompt
from main import BUILTIN_PROMPTS
from tracer import TRACE_FILE, setup_tracer

try:
    from google.adk.agents import LlmAgent  # noqa: F401
    _ADK_AVAILABLE = True
except ImportError:
    _ADK_AVAILABLE = False

from tokenclock_agent.runner import optimize_prompt

HERE = Path(__file__).resolve().parent
DASHBOARD_DIST = HERE.parent / "dashboard" / "dist"
PORT = int(os.getenv("PORT", "5000"))

# One tracer/provider for the server's lifetime; runs append to spans.jsonl.
TRACER, PROVIDER = setup_tracer()
_run_lock = threading.Lock()

app = Flask(__name__, static_folder=str(DASHBOARD_DIST), static_url_path="")


# ----------------------------- trace parsing ------------------------------
def _trace_id(span):
    return (span.get("context") or {}).get("trace_id") or span.get("trace_id")


def _status_code(span):
    st = span.get("status") or {}
    return st.get("status_code") or st.get("code")


def _ms(start, end):
    try:
        s = datetime.fromisoformat(start.replace("Z", "+00:00"))
        e = datetime.fromisoformat(end.replace("Z", "+00:00"))
        return round((e - s).total_seconds() * 1000, 2)
    except (AttributeError, ValueError):
        return 0


def parse_runs(path):
    if not Path(path).exists():
        return []
    by_trace = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                span = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = _trace_id(span)
            if tid:
                by_trace.setdefault(tid, []).append(span)

    runs = []
    for spans in by_trace.values():
        root = next((s for s in spans if s["name"] == "llm.full_pipeline"), None)
        if not root:
            continue
        inf = next((s for s in spans if s["name"] == "llm.inference"), None)
        prep = next((s for s in spans if s["name"] == "llm.prompt_preparation"), None)
        post = next((s for s in spans if s["name"] == "llm.post_processing"), None)
        ra = root.get("attributes") or {}
        ia = (inf or {}).get("attributes") or {}
        pa = (prep or {}).get("attributes") or {}
        poa = (post or {}).get("attributes") or {}

        err_msg = None
        for s in spans:
            for ev in (s.get("events") or []):
                if ev.get("name") == "exception":
                    err_msg = (ev.get("attributes") or {}).get("exception.message")
                    break
        has_err = (ra.get("pipeline.success") is False
                   or err_msg is not None
                   or any(_status_code(s) == "ERROR" for s in spans))
        # Quota-exhausted (429) runs are infrastructure limits, not system
        # behavior — flag them so the UI can color and exclude them.
        quota = has_err and ("RESOURCE_EXHAUSTED" in (err_msg or "")
                             or "429" in (err_msg or ""))

        runs.append({
            "traceId": _trace_id(root),
            "timestamp": root.get("start_time"),
            "prompt": ra.get("prompt.text", "—"),
            "model": ra.get("model.name", "—"),
            "success": not has_err,
            "quota": quota,
            "errorMsg": err_msg,
            "totalMs": _ms(root.get("start_time"), root.get("end_time")),
            "inferenceMs": ia.get("inference.duration_ms", 0),
            "prepMs": pa.get("stage.duration_ms", 0),
            "postMs": poa.get("stage.duration_ms", 0),
            "totalTokens": ia.get("tokens.total") or ra.get("pipeline.total_tokens") or 0,
            "promptTokens": ia.get("tokens.prompt", 0),
            "completionTokens": ia.get("tokens.completion", 0),
        })
    runs.sort(key=lambda r: r["timestamp"] or "")
    return runs


# -------------------------------- API -------------------------------------
@app.get("/api/traces")
def api_traces():
    return jsonify({"runs": parse_runs(TRACE_FILE)})


@app.get("/api/health")
def api_health():
    mcp = check_mcp_readiness()
    return jsonify({
        "dynatrace": check_readiness(),
        "dynatrace_mcp": mcp,
        "google": usage.status(llm_client._KEYS),
        "agent": {
            "adk_available": _ADK_AVAILABLE,
            "dynatrace_mcp_stub": mcp.get("stub", True),
            "dynatrace_mcp_healthy": mcp.get("healthy", False),
            "dynatrace_mcp_status": mcp.get("status"),
            "model": os.getenv("MODEL_NAME", "gemini-2.5-flash"),
        },
    })


@app.post("/api/run")
def api_run():
    data = request.get_json(force=True, silent=True) or {}
    mode = data.get("mode", "auto")

    if mode == "single":
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            return jsonify({"ok": False, "error": "Prompt is empty."}), 400
        prompts = [prompt]
    else:
        prompts = BUILTIN_PROMPTS

    if not _run_lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "A test run is already in progress."}), 409

    results = []
    try:
        for p in prompts:
            try:
                r = run_traced_prompt(TRACER, p)
                results.append({"prompt": p, "ok": True, "tokens": r["tokens"]})
            except Exception as e:  # one failed prompt shouldn't abort the batch
                results.append({"prompt": p, "ok": False, "error": str(e)})
        PROVIDER.force_flush()
    finally:
        _run_lock.release()

    return jsonify({"ok": True, "mode": mode, "results": results})


@app.post("/api/optimize")
def api_optimize():
    """Run the ADK agent to analyze and rewrite a prompt for lower tokens/latency."""
    if not _ADK_AVAILABLE:
        return jsonify({
            "ok": False,
            "error": "google-adk is not installed. Run: pip install -r requirements.txt",
        }), 503

    data = request.get_json(force=True, silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "Prompt is empty."}), 400

    if not _run_lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "A run is already in progress."}), 409

    try:
        result = optimize_prompt(prompt, tracer=TRACER, provider=PROVIDER)
        if result.error and not result.final_text:
            return jsonify({"ok": False, "error": result.error}), 500
        return jsonify({
            "ok": True,
            "report": result.final_text,
            "events": result.events,
            "stub_mcp": result.stub_mcp,
            "error": result.error,
        })
    finally:
        _run_lock.release()


# ----------------------------- static app ---------------------------------
@app.get("/")
def index():
    if not (DASHBOARD_DIST / "index.html").exists():
        return ("Dashboard not built. Run: cd dashboard && npm install && npm run build",
                503)
    return send_from_directory(DASHBOARD_DIST, "index.html")


def _open_browser():
    webbrowser.open(f"http://127.0.0.1:{PORT}")


if __name__ == "__main__":
    threading.Timer(1.2, _open_browser).start()
    print(f"\nPrompt Latency Tracer running at http://127.0.0.1:{PORT}\n")
    app.run(host="127.0.0.1", port=PORT, threaded=True)
