"""Run the TokenClock ADK agent from Flask or CLI."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any

from tokenclock_agent.agent import build_agent
from tokenclock_agent.tools import bind_tracer

try:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    _ADK_AVAILABLE = True
except ImportError:
    _ADK_AVAILABLE = False


@dataclass
class OptimizeResult:
    final_text: str
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


async def _ainvoke(prompt: str, *, tracer, provider, model: str | None) -> OptimizeResult:
    agent = build_agent(model=model)
    if agent is None or not _ADK_AVAILABLE:
        return OptimizeResult(
            final_text="google-adk is not installed. Run: pip install -r requirements.txt",
            error="ADK not available",
        )

    bind_tracer(tracer, provider)

    session_service = InMemorySessionService()
    app_name = "tokenclock"
    user_id = os.getenv("USER", "demo")
    session = await session_service.create_session(app_name=app_name, user_id=user_id)
    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)

    question = (
        f"Optimize this prompt for lower latency and token usage while preserving meaning:\n\n"
        f"{prompt}"
    )
    content = types.Content(role="user", parts=[types.Part(text=question)])
    events: list[dict[str, Any]] = []
    final_text = ""

    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            ev: dict[str, Any] = {
                "author": getattr(event, "author", None),
                "is_final": event.is_final_response() if hasattr(event, "is_final_response") else False,
            }
            if hasattr(event, "content") and event.content is not None:
                parts = getattr(event.content, "parts", []) or []
                ev["text"] = "".join(getattr(p, "text", "") or "" for p in parts)
                if ev["is_final"]:
                    final_text = ev["text"]
            events.append(ev)
    except Exception as e:
        return OptimizeResult(final_text="", events=events, error=str(e))
    finally:
        provider.force_flush()

    return OptimizeResult(final_text=final_text, events=events)


def optimize_prompt(prompt: str, *, tracer, provider, model: str | None = None) -> OptimizeResult:
    """Synchronous entry point for the Flask server."""
    return asyncio.run(_ainvoke(prompt, tracer=tracer, provider=provider, model=model))
