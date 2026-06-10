"""Local Dynatrace MCP stub for prompt-efficiency demos.

Exposes the same tool surface as the official @dynatrace-oss/dynatrace-mcp-server
(list_problems, execute_dql, generate_dql_from_natural_language, find_entity_by_name)
but answers from local spans.jsonl when possible.

Run with: python -m tokenclock_agent.mcp_stub
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from tokenclock_agent.trace_reader import load_runs, summarize_runs

SERVER = Server("dynatrace-stub")


@SERVER.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="execute_dql",
            description=(
                "Run a Dynatrace Query Language (DQL) statement against Grail. "
                "Use for historical prompt latency and token usage patterns."
            ),
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        ),
        Tool(
            name="generate_dql_from_natural_language",
            description="Convert an English question into a runnable DQL query.",
            inputSchema={
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        ),
        Tool(
            name="list_problems",
            description="List open problems detected by Dynatrace Davis AI.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_age_hours": {"type": "number", "default": 24},
                },
            },
        ),
        Tool(
            name="find_entity_by_name",
            description="Resolve a service name to a Dynatrace entity ID.",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        ),
    ]


def _dql_response(query: str) -> dict[str, Any]:
    runs = load_runs()
    summary = summarize_runs(runs)
    q = query.lower()

    if "token" in q or "latency" in q or "prompt" in q or "span" in q:
        records = [
            {
                "timestamp": r["timestamp"],
                "service": "prompt-latency-tracer",
                "prompt_preview": r["prompt"][:120],
                "total_ms": r["total_ms"],
                "inference_ms": r["inference_ms"],
                "total_tokens": r["total_tokens"],
                "prompt_tokens": r["prompt_tokens"],
                "completion_tokens": r["completion_tokens"],
                "model": r["model"],
            }
            for r in runs[-20:]
        ]
        return {"summary": summary, "records": records}

    return {"summary": summary, "records": runs[-5:]}


def _generate_dql(question: str) -> dict[str, str]:
    q = question.lower()
    if "token" in q:
        dql = (
            'fetch spans, from: now()-7d\n'
            '| filter service.name == "prompt-latency-tracer"\n'
            '| summarize avg(tokens.total), p95(duration_ms) by prompt.text\n'
            '| sort avg(tokens.total) desc\n'
            '| limit 20'
        )
    elif "latency" in q or "slow" in q:
        dql = (
            'fetch spans, from: now()-7d\n'
            '| filter service.name == "prompt-latency-tracer"\n'
            '| summarize p50(duration_ms), p95(duration_ms) by model.name\n'
            '| sort p95(duration_ms) desc'
        )
    else:
        dql = (
            'fetch spans, from: now()-24h\n'
            '| filter service.name == "prompt-latency-tracer"\n'
            '| fields prompt.text, tokens.total, duration_ms\n'
            '| limit 50'
        )
    return {"dql": dql}


@SERVER.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "execute_dql":
        payload = _dql_response(arguments.get("query", ""))
    elif name == "generate_dql_from_natural_language":
        payload = _generate_dql(arguments.get("question", ""))
    elif name == "list_problems":
        payload = {
            "problems": [{
                "id": "P-TOKEN-001",
                "title": "High prompt token usage on verbose benchmark prompts",
                "severity": "LOW",
                "root_cause_summary": (
                    "Several llm.inference spans show prompt_tokens > 15 with "
                    "open-ended instructions. Shorter, scoped prompts reduce "
                    "both latency and completion token volume."
                ),
            }]
        }
    elif name == "find_entity_by_name":
        name_arg = (arguments.get("name") or "").lower()
        entities = {"prompt-latency-tracer": "SERVICE-TOKENCLOCK001"}
        payload = {"entity_id": entities.get(name_arg), "name": arguments.get("name")}
    else:
        payload = {"error": f"unknown tool {name!r}"}

    return [TextContent(type="text", text=json.dumps(payload, indent=2, default=str))]


async def _main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await SERVER.run(
            read_stream,
            write_stream,
            SERVER.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
