"""ADK FunctionTools for measuring prompt latency and token usage."""

from __future__ import annotations

from typing import Any

from llm_client import run_traced_prompt

# Set by runner before each agent invocation.
_tracer = None
_provider = None


def bind_tracer(tracer, provider) -> None:
    global _tracer, _provider
    _tracer = tracer
    _provider = provider


def measure_prompt(prompt: str) -> dict[str, Any]:
    """Run a prompt through the traced Gemini pipeline and return latency and token metrics.

    Use this to capture a baseline before optimizing, and again after proposing a rewrite
    to verify token and latency savings.

    Args:
        prompt: The exact prompt text to send to Gemini.

    Returns:
        Dict with prompt, response preview, tokens, latency breakdown (ms), and success flag.
    """
    if _tracer is None:
        return {"error": "Tracer not initialized — call bind_tracer() first."}
    try:
        result = run_traced_prompt(_tracer, prompt)
        if _provider is not None:
            _provider.force_flush()
        lat = result["latency"]
        return {
            "success": True,
            "prompt": prompt,
            "response_preview": result["response"][:300],
            "tokens": result["tokens"],
            "latency_ms": lat,
            "total_ms": lat["total_ms"],
            "inference_ms": lat["inference_ms"],
        }
    except Exception as e:
        if _provider is not None:
            _provider.force_flush()
        return {"success": False, "prompt": prompt, "error": str(e)}
