# check_dynatrace_mcp.py
"""
Dynatrace MCP readiness check for the TokenClock ADK agent.

This is separate from check_dynatrace.py (OTLP trace ingest). MCP uses the
hosted MCP gateway on *.apps.dynatrace.com with a Platform Token (Bearer) and
scopes like mcp-gateway:servers:invoke — not the OTLP ingest API.

Usage:
    python check_dynatrace_mcp.py
"""
from __future__ import annotations

import json
import os
import re
import ssl
import urllib.error
import urllib.request

from dotenv import load_dotenv

from env_bootstrap import ensure_env

ensure_env()
load_dotenv()

MCP_GATEWAY_SCOPES = (
    "mcp-gateway:servers:invoke",
    "mcp-gateway:servers:read",
)
MCP_TOOL_SCOPES = (
    "davis-copilot:nl2dql:execute",
    "storage:buckets:read",
)

try:
    import certifi

    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()


def _use_stub() -> bool:
    return os.getenv("DYNATRACE_MCP_STUB", "1").strip().lower() not in {"0", "false", "no"}


def _platform_token() -> str:
    return (os.getenv("DT_PLATFORM_TOKEN") or os.getenv("DYNATRACE_API_TOKEN") or "").strip()


def _env_id_from_url(url: str) -> str | None:
    m = re.search(r"https://([^.]+)\.(?:live|apps)\.dynatrace\.com", url)
    return m.group(1) if m else None


def _derive_mcp_url() -> str:
    explicit = os.getenv("DYNATRACE_MCP_URL", "").strip()
    if explicit:
        return explicit
    for var in ("DT_ENVIRONMENT_URL", "DYNATRACE_ENDPOINT"):
        env_id = _env_id_from_url(os.getenv(var, ""))
        if env_id:
            return (
                f"https://{env_id}.apps.dynatrace.com/platform-reserved/"
                f"mcp-gateway/v0.1/servers/dynatrace-mcp/mcp"
            )
    return ""


def _connection_mode() -> str:
    if _use_stub():
        return "stub"
    if os.getenv("DYNATRACE_MCP_URL", "").strip():
        return "hosted_http"
    if os.getenv("DT_ENVIRONMENT_URL", "").strip() and not os.getenv("DYNATRACE_MCP_URL", "").strip():
        # Agent can use npx OSS server; gateway probe still validates the tenant token.
        return "oss_stdio"
    if _derive_mcp_url():
        return "hosted_http"
    return "unconfigured"


def _request(url: str, headers: dict, data: bytes | None = None, method: str = "GET") -> tuple[int, object]:
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
            raw = resp.read().decode(errors="replace")
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return e.code, raw
    except urllib.error.URLError as e:
        return 0, str(e)


def _api_base_from_mcp_url(mcp_url: str) -> str:
    env_id = _env_id_from_url(mcp_url)
    if env_id:
        return f"https://{env_id}.live.dynatrace.com/api/v2"
    return ""


def _lookup_token_scopes(api_base: str, token: str) -> dict | None:
    """Classic apiTokens/lookup — works for some tokens, not all platform tokens."""
    headers = {
        "Authorization": f"Api-Token {token}",
        "Content-Type": "application/json",
    }
    body = json.dumps({"token": token}).encode()
    status, resp = _request(f"{api_base}/apiTokens/lookup", headers, body, method="POST")
    if status == 200 and isinstance(resp, dict):
        return resp
    return None


def _probe_mcp_gateway(mcp_url: str, token: str) -> dict:
    """
    Send a minimal MCP initialize over Streamable HTTP. Auth/scopes are checked
    before the session is accepted, so status codes are informative.
    """
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "tokenclock-mcp-check", "version": "1.0.0"},
        },
    }).encode()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    status, body = _request(mcp_url, headers, payload, method="POST")
    raw = body if isinstance(body, str) else json.dumps(body)
    snippet = raw[:240].replace("\n", " ")

    if status in (200, 202):
        return {
            "status": "healthy",
            "healthy": True,
            "message": "MCP gateway accepted the token (initialize succeeded).",
        }
    if status == 401:
        return {
            "status": "error",
            "healthy": False,
            "message": "Token rejected (401). Use a Platform Token as Bearer, not a classic Api-Token.",
        }
    if status == 403:
        return {
            "status": "needs_access",
            "healthy": False,
            "message": (
                "Token authenticated but missing MCP gateway scopes "
                f"({', '.join(MCP_GATEWAY_SCOPES)}). {snippet}"
            ),
        }
    if status == 0:
        return {"status": "error", "healthy": False, "message": f"Network error: {snippet}"}
    return {
        "status": "error",
        "healthy": False,
        "message": f"MCP gateway returned HTTP {status}: {snippet}",
    }


def check_mcp_readiness() -> dict:
    """
    Returns a structured MCP readiness verdict for the agent.

    status: stub | healthy | needs_access | not_configured | error
    healthy: True when live MCP will work (or stub mode is intentionally on).
    """
    stub = _use_stub()
    mode = _connection_mode()
    token = _platform_token()
    mcp_url = _derive_mcp_url()

    result: dict = {
        "stub": stub,
        "mode": mode,
        "mcp_url": mcp_url or None,
        "missing_scopes": [],
    }

    if stub:
        return {
            **result,
            "status": "stub",
            "healthy": True,
            "message": (
                "Local MCP stub active (DYNATRACE_MCP_STUB=1). Agent runs without a "
                "Dynatrace tenant. Set DYNATRACE_MCP_STUB=0 + Platform Token for live MCP."
            ),
        }

    if mode == "oss_stdio":
        env_url = os.getenv("DT_ENVIRONMENT_URL", "").strip()
        if not env_url or not token:
            return {
                **result,
                "status": "not_configured",
                "healthy": False,
                "message": "Set DT_ENVIRONMENT_URL and DT_PLATFORM_TOKEN (or DYNATRACE_API_TOKEN).",
            }
        result["mode"] = "oss_stdio"
        result["mcp_url"] = mcp_url or None

    if not token:
        return {
            **result,
            "status": "not_configured",
            "healthy": False,
            "message": "Set DT_PLATFORM_TOKEN or DYNATRACE_API_TOKEN (Platform Token, Bearer).",
        }

    if not mcp_url:
        return {
            **result,
            "status": "not_configured",
            "healthy": False,
            "message": (
                "Set DYNATRACE_MCP_URL or DT_ENVIRONMENT_URL / DYNATRACE_ENDPOINT "
                "so we can derive the MCP gateway URL."
            ),
        }

    # Scope introspection when the classic lookup API works.
    api_base = _api_base_from_mcp_url(mcp_url)
    if api_base:
        lookup = _lookup_token_scopes(api_base, token)
        if lookup:
            scopes = lookup.get("scopes") or []
            missing = [s for s in MCP_GATEWAY_SCOPES if s not in scopes]
            result["token"] = lookup.get("name")
            result["scopes"] = scopes
            result["missing_scopes"] = missing
            if missing:
                return {
                    **result,
                    "status": "needs_access",
                    "healthy": False,
                    "message": f"Missing MCP scopes: {', '.join(missing)}",
                }

    probe = _probe_mcp_gateway(mcp_url, token)
    return {**result, **probe}


def main():
    print("=" * 64)
    print("Dynatrace MCP readiness check (agent tools)")
    print("=" * 64)
    r = check_mcp_readiness()
    print(f"status   : {r['status'].upper()}")
    print(f"mode     : {r.get('mode', '?')}")
    print(f"stub     : {'yes' if r.get('stub') else 'no'}")
    if r.get("mcp_url"):
        print(f"mcp url  : {r['mcp_url']}")
    if r.get("token"):
        print(f"token    : {r['token']}")
    if r.get("scopes"):
        print(f"scopes   : {', '.join(r['scopes'])}")
    if r.get("missing_scopes"):
        print(f"missing  : {', '.join(r['missing_scopes'])}")
    print(f"ready    : {'YES' if r['healthy'] else 'NO'}")
    print(f"detail   : {r['message']}")
    print()
    print("Note: OTLP trace export is checked separately — run: python check_dynatrace.py")


if __name__ == "__main__":
    main()
