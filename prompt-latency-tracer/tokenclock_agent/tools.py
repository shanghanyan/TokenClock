"""ADK FunctionTools for measuring prompts and reading local trace history."""

from __future__ import annotations

from typing import Any

from llm_client import run_traced_prompt
from tokenclock_agent.trace_reader import load_runs, summarize_runs

_tracer = None
_provider = None
_measurements: list[dict[str, Any]] = []


def bind_tracer(tracer, provider) -> None:
    global _tracer, _provider
    _tracer = tracer
    _provider = provider


def reset_measurements() -> None:
    _measurements.clear()


def get_measurements() -> list[dict[str, Any]]:
    return list(_measurements)


def measure_prompt(prompt: str) -> dict[str, Any]:
    """Run a prompt through the traced Gemini pipeline and return latency and token metrics.

    Use for a baseline before optimizing and again on the rewritten prompt to verify savings.

    Args:
        prompt: The exact prompt text to send to Gemini.

    Returns:
        Dict with prompt, response preview, tokens, latency breakdown (ms), and success flag.
    """
    if _tracer is None:
        return {"error": "Tracer not initialized."}
    try:
        result = run_traced_prompt(_tracer, prompt)
        if _provider is not None:
            _provider.force_flush()
        lat = result["latency"]
        out = {
            "success": True,
            "prompt": prompt,
            "response_preview": result["response"][:300],
            "tokens": result["tokens"],
            "latency_ms": lat,
            "total_ms": lat["total_ms"],
            "inference_ms": lat["inference_ms"],
        }
        _measurements.append(out)
        return out
    except Exception as e:
        if _provider is not None:
            _provider.force_flush()
        out = {"success": False, "prompt": prompt, "error": str(e)}
        _measurements.append(out)
        return out


def get_trace_history(limit: int = 20) -> dict[str, Any]:
    """Return recent prompt runs from the local trace file with aggregate stats.

    Use this to see how past prompts performed (tokens, latency) before suggesting
    optimizations. Data comes from traces/spans.jsonl on disk.

    Args:
        limit: Maximum number of recent runs to include (default 20).

    Returns:
        Summary statistics plus a list of recent runs with prompt preview and metrics.
    """
    runs = load_runs()
    summary = summarize_runs(runs)
    recent = [
        {
            "timestamp": r["timestamp"],
            "prompt_preview": r["prompt"][:120],
            "total_ms": r["total_ms"],
            "inference_ms": r["inference_ms"],
            "total_tokens": r["total_tokens"],
            "prompt_tokens": r["prompt_tokens"],
            "completion_tokens": r["completion_tokens"],
            "model": r["model"],
            "success": r["success"],
        }
        for r in runs[-limit:]
    ]
    return {"summary": summary, "recent_runs": recent, "total_runs_on_disk": len(runs)}
