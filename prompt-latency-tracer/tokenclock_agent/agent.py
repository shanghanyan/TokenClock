"""Google Cloud Agent Builder (ADK) agent wired to Dynatrace MCP."""

from __future__ import annotations

import os
import sys
from typing import Any

try:
    from google.adk.agents import LlmAgent
    from google.adk.tools import FunctionTool
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StdioConnectionParams,
        StreamableHTTPConnectionParams,
    )
    from mcp import StdioServerParameters

    from tokenclock_agent.tools import measure_prompt

    _ADK_AVAILABLE = True
except ImportError:
    _ADK_AVAILABLE = False

SYSTEM_PROMPT = """\
You are TokenClock, a prompt-efficiency agent built with Google Cloud Agent Builder
(ADK) and Gemini. Your mission: reduce prompt latency and token usage while
preserving the user's intent.

Follow this workflow for every request:
1. Call `measure_prompt` on the user's original prompt to capture baseline tokens
   and latency (prep / inference / post ms).
2. Use Dynatrace MCP tools to gather context:
   - `generate_dql_from_natural_language` to build a query about historical prompt
     token/latency patterns.
   - `execute_dql` to run it and see what similar prompts cost.
   - Optionally `list_problems` for Davis AI insights on verbose prompts.
3. Analyze why the prompt is slow or token-heavy (redundant words, open-ended
   phrasing, unnecessary context, missing output constraints, etc.).
4. Write an optimized prompt that should be shorter or more constrained while
   keeping the same meaning. Explain each edit briefly.
5. Call `measure_prompt` on your optimized prompt to verify savings.
6. Return a concise report with these sections:
   ## Summary
   One line on whether optimization succeeded.
   ## Metrics
   Table: original vs optimized — total tokens, inference ms, total ms.
   ## Optimized prompt
   The rewritten prompt in a fenced block.
   ## Changes
   Bullets explaining edits and why they help.
   ## Meaning preserved?
   Honest assessment of any trade-offs.

Never skip the baseline measurement or the verification run. Cite numbers from
tool outputs; do not invent metrics.
"""


def _use_stub() -> bool:
    return os.getenv("DYNATRACE_MCP_STUB", "1").strip().lower() not in {"0", "false", "no"}


def _dynatrace_toolset() -> Any:
    if not _ADK_AVAILABLE:
        raise ImportError("google-adk and mcp must be installed: pip install google-adk mcp")

    mcp_url = os.getenv("DYNATRACE_MCP_URL", "").strip()
    platform_token = os.getenv("DT_PLATFORM_TOKEN", os.getenv("DYNATRACE_API_TOKEN", "")).strip()

    if not _use_stub() and mcp_url and platform_token:
        return McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=mcp_url,
                headers={"Authorization": f"Bearer {platform_token}"},
            ),
        )

    if not _use_stub() and os.getenv("DT_ENVIRONMENT_URL", "").strip() and platform_token:
        return McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="npx",
                    args=["-y", "@dynatrace-oss/dynatrace-mcp-server"],
                    env={
                        **os.environ,
                        "DT_ENVIRONMENT_URL": os.environ["DT_ENVIRONMENT_URL"],
                        "DT_PLATFORM_TOKEN": platform_token,
                    },
                ),
            ),
        )

    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", "tokenclock_agent.mcp_stub"],
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            ),
        ),
    )


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
            _dynatrace_toolset(),
        ],
    )
