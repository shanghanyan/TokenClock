# server.py
"""
TokenClock web app: React dashboard + API for tracing and prompt optimization.

    python server.py     # http://127.0.0.1:5001  (5000 is often taken by macOS AirPlay)
"""
import json
import os
import socket
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

import usage
import llm_client  # loads .env via env.py
from llm_client import run_traced_prompt
from main import BUILTIN_PROMPTS
from tracer import TRACE_FILE, clear_traces, delete_trace, setup_tracer

try:
    from google.adk.agents import LlmAgent  # noqa: F401
    _ADK_AVAILABLE = True
except ImportError:
    _ADK_AVAILABLE = False

from tokenclock_agent.runner import optimize_prompt
from tokenclock_agent.report_parser import resolve_optimized_prompt
from optimization_store import clear_optimizations, load_optimizations, save_optimization

HERE = Path(__file__).resolve().parent
DASHBOARD_DIST = HERE.parent / "dashboard" / "dist"


def _pick_port(preferred: int) -> int:
    """Use preferred port, or the next free port on 127.0.0.1 (macOS AirPlay often owns 5000)."""
    for port in range(preferred, preferred + 10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred


PREFERRED_PORT = int(os.getenv("PORT", "5001"))
PORT = _pick_port(PREFERRED_PORT)

TRACER, PROVIDER = setup_tracer()
_run_lock = threading.Lock()

app = Flask(__name__, static_folder=str(DASHBOARD_DIST), static_url_path="")


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
        quota = has_err and ("RESOURCE_EXHAUSTED" in (err_msg or "")
                             or "429" in (err_msg or ""))

        runs.append({
            "traceId": _trace_id(root),
            "timestamp": root.get("start_time"),
            "prompt": ra.get("prompt.full") or ra.get("prompt.text", "—"),
            "promptPreview": ra.get("prompt.text", "—"),
            "optimizationRole": ra.get("optimization.role"),
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


def _optimized_text(opt: dict) -> str:
    return (
        resolve_optimized_prompt(opt.get("report", ""), opt.get("metrics"))
        or opt.get("optimized_prompt")
        or ""
    ).strip()


def enrich_runs_with_optimizations(runs: list[dict], optimizations: list[dict]) -> None:
    """Attach original/optimized prompt text to trace runs from optimization history."""
    for run in runs:
        run["originalPrompt"] = None
        run["optimizedPrompt"] = None
        p = (run.get("prompt") or run.get("promptPreview") or "").strip()
        if not p:
            continue
        for opt in optimizations:
            orig = (opt.get("original_prompt") or "").strip()
            opt_text = _optimized_text(opt)
            baseline_p = ((opt.get("metrics") or {}).get("baseline") or {}).get("prompt", "")
            optimized_p = ((opt.get("metrics") or {}).get("optimized") or {}).get("prompt", "")
            if p in {orig, opt_text, baseline_p, optimized_p} or (
                orig and (orig.startswith(p) or p.startswith(orig[:200]))
            ):
                run["originalPrompt"] = orig or baseline_p or None
                run["optimizedPrompt"] = opt_text or optimized_p or None
                run["optimizationSavings"] = (opt.get("metrics") or {}).get("savings")
                break
        if run["optimizationRole"] == "baseline" and not run["originalPrompt"]:
            run["originalPrompt"] = p
        if run["optimizationRole"] == "optimized" and not run["optimizedPrompt"]:
            run["optimizedPrompt"] = p


@app.get("/api/traces")
def api_traces():
    optimizations = load_optimizations()
    runs = parse_runs(TRACE_FILE)
    enrich_runs_with_optimizations(runs, optimizations)
    return jsonify({"runs": runs})


@app.post("/api/traces/delete")
def api_delete_trace():
    """Remove one trace run by traceId."""
    data = request.get_json(force=True, silent=True) or {}
    trace_id = (data.get("traceId") or "").strip()
    if not trace_id:
        return jsonify({"ok": False, "error": "traceId is required."}), 400
    if not _run_lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "A run is in progress — try again shortly."}), 409
    try:
        if not delete_trace(trace_id):
            return jsonify({"ok": False, "error": "Trace not found."}), 404
        return jsonify({"ok": True, "traceId": trace_id})
    finally:
        _run_lock.release()


@app.post("/api/traces/clear")
def api_clear_traces():
    """Remove stored prompt run data only; does not affect other API routes."""
    if not _run_lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "A run is in progress — try again shortly."}), 409
    try:
        removed = clear_traces()
        return jsonify({"ok": True, "removed": removed})
    finally:
        _run_lock.release()


@app.get("/api/health")
def api_health():
    return jsonify({
        "google": usage.status(llm_client._KEYS),
        "agent": {
            "adk_available": _ADK_AVAILABLE,
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
            except Exception as e:
                results.append({"prompt": p, "ok": False, "error": str(e)})
        PROVIDER.force_flush()
    finally:
        _run_lock.release()

    return jsonify({"ok": True, "mode": mode, "results": results})


@app.post("/api/optimize")
def api_optimize():
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
        record = save_optimization(
            original_prompt=prompt,
            optimized_prompt=resolve_optimized_prompt(result.final_text, result.metrics),
            metrics=result.metrics,
            report=result.final_text,
        )
        return jsonify({
            "ok": True,
            "id": record["id"],
            "timestamp": record["timestamp"],
            "original_prompt": prompt,
            "report": result.final_text,
            "metrics": result.metrics,
            "optimized_prompt": record["optimized_prompt"],
            "measurements": result.measurements,
            "events": result.events,
            "error": result.error,
        })
    finally:
        _run_lock.release()


@app.get("/api/optimizations")
def api_optimizations():
    runs = []
    for row in load_optimizations():
        row = dict(row)
        row["optimized_prompt"] = resolve_optimized_prompt(row.get("report", ""), row.get("metrics")) or row.get("optimized_prompt")
        runs.append(row)
    return jsonify({"runs": runs})


@app.post("/api/optimizations/clear")
def api_clear_optimizations():
    if not _run_lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "A run is in progress — try again shortly."}), 409
    try:
        removed = clear_optimizations()
        return jsonify({"ok": True, "removed": removed})
    finally:
        _run_lock.release()


@app.get("/")
def index():
    if not (DASHBOARD_DIST / "index.html").exists():
        return ("Dashboard not built. Run: cd dashboard && npm install && npm run build", 503)
    return send_from_directory(DASHBOARD_DIST, "index.html")


if __name__ == "__main__":
    url = f"http://127.0.0.1:{PORT}"
    if PORT != PREFERRED_PORT:
        print(f"\n[port] {PREFERRED_PORT} unavailable — using {PORT} instead.")
        if PREFERRED_PORT == 5000:
            print("[port] On macOS, disable AirPlay Receiver (System Settings → AirDrop & Handoff)")
            print("       or set PORT=5001 in .env.\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"\nTokenClock running at {url}\n")
    app.run(host="127.0.0.1", port=PORT, threaded=True)
