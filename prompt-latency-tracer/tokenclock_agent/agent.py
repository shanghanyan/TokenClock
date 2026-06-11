"""Google ADK agent for prompt efficiency — local tools only."""

from __future__ import annotations

import os
from typing import Any

try:
    from google.adk.agents import LlmAgent
    from google.adk.tools import FunctionTool

    from tokenclock_agent.tools import get_trace_history, measure_prompt

    _ADK_AVAILABLE = True
except ImportError:
    _ADK_AVAILABLE = False

SYSTEM_PROMPT = """\
You are TokenClock, a prompt-efficiency agent powered by Gemini. Your mission:
reduce prompt latency and token usage while preserving the user's intent.

Follow this workflow for every request:
1. Call `get_trace_history` to see how similar past prompts performed locally.
2. Call `measure_prompt` on the user's original prompt for baseline tokens and latency.
3. Analyze why the prompt is slow or token-heavy (verbosity, open-ended phrasing,
   missing output constraints, redundant context, etc.).
4. Write an optimized prompt that should be shorter or more constrained while keeping
   the same meaning. Explain each edit briefly.
5. Call `measure_prompt` on your optimized prompt to verify savings.
6. Return a concise report:
   ## Summary — one line on whether optimization succeeded.
   ## Metrics — original vs optimized: total tokens, inference ms, total ms.
   ## Optimized prompt — rewritten text in a fenced block.
   ## Changes — bullets explaining edits.
   ## Meaning preserved? — honest trade-offs if any.

Never skip baseline or verification measurements. Cite numbers from tool outputs only.
"""


def build_agent(model: str | None = None) -> Any:
    """Construct the ADK LlmAgent. Returns None if ADK is unavailable."""
    if not _ADK_AVAILABLE:
        return None
    model = model or os.getenv("MODEL_NAME", "gemini-2.5-flash")
    return LlmAgent(
        model=model,
        name="tokenclock_agent",
        instruction=SYSTEM_PROMPT,
        tools=[
            FunctionTool(measure_prompt),
            FunctionTool(get_trace_history),
        ],
    )
