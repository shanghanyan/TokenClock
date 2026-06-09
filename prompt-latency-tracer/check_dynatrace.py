# check_dynatrace.py
"""
Dynatrace readiness check (Path 2).

Uses the one capability our personal access token actually has (token lookup via
the apiTokens API) to report whether trace ingest is possible from this
environment, and exactly which scope is missing if not.

Usage:
    python check_dynatrace.py
"""
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

INGEST_SCOPE = "openTelemetryTrace.ingest"

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()


def _api_base(endpoint: str) -> str:
    """Derive the .../api/v2 base from the OTLP endpoint."""
    marker = "/api/v2"
    i = endpoint.find(marker)
    return endpoint[: i + len(marker)] if i >= 0 else endpoint.rstrip("/")


def _traces_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    return endpoint if endpoint.endswith("/v1/traces") else f"{endpoint}/v1/traces"


def _auth_header(token: str) -> dict:
    scheme = os.getenv("DYNATRACE_AUTH_SCHEME", "Api-Token")
    prefix = "Bearer" if scheme.lower() == "bearer" else "Api-Token"
    return {"Authorization": f"{prefix} {token}"}


def _request(url, headers, data, method="POST") -> tuple[int, object]:
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except urllib.error.URLError as e:
        return 0, str(e)


def _post(url: str, token: str, body: dict) -> tuple[int, object]:
    headers = {"Authorization": f"Api-Token {token}", "Content-Type": "application/json"}
    return _request(url, headers, json.dumps(body).encode())


def _probe_ingest(endpoint: str, token: str) -> dict:
    """
    Fallback when token introspection isn't possible (e.g. an ingest-only token
    without apiTokens.read). Sends an empty body to the OTLP traces endpoint:
    auth/scope are evaluated before the payload, so the status code tells us
    whether ingest would work.
    """
    headers = {**_auth_header(token), "Content-Type": "application/x-protobuf"}
    status, body = _request(_traces_url(endpoint), headers, b"")
    raw = body if isinstance(body, str) else json.dumps(body)
    # OTLP error bodies are protobuf-framed; pull out the human-readable text.
    printable = "".join(c for c in raw if c.isprintable())
    m = re.search(r"[A-Z][a-z].*", printable)
    text = (m.group(0) if m else printable).strip()[:200]
    if status in (200, 204, 400):  # 400 = authenticated+scoped, just an empty/invalid payload
        return {"status": "healthy", "healthy": True,
                "message": "Ready — token accepted by the OTLP ingest endpoint."}
    if status == 401:
        return {"status": "error", "healthy": False,
                "message": "Token authentication failed (invalid/expired)."}
    if status == 403:
        return {"status": "needs_access", "healthy": False,
                "message": f"Missing ingest scope. {text}"}
    if status == 0:
        return {"status": "error", "healthy": False, "message": f"Network error: {text}"}
    return {"status": "error", "healthy": False, "message": f"HTTP {status}: {text}"}


def check_readiness() -> dict:
    """
    Returns a structured Dynatrace readiness verdict for the configured token.

    status is one of: healthy | needs_access | not_configured | error
    healthy=True only when trace ingest will actually work.
    """
    endpoint = os.getenv("DYNATRACE_ENDPOINT", "")
    token = os.getenv("DYNATRACE_API_TOKEN", "")
    export_enabled = os.getenv("DYNATRACE_ENABLED") == "1"

    def finish(result: dict) -> dict:
        result["export_enabled"] = export_enabled
        result["exporting"] = bool(export_enabled and result.get("healthy"))
        return result

    if not endpoint or not token:
        return finish({
            "status": "not_configured",
            "healthy": False,
            "message": "Set DYNATRACE_ENDPOINT and DYNATRACE_API_TOKEN in .env",
        })

    # Step 1: introspect the token (works for tokens with apiTokens.read/write,
    # e.g. the personal token). Gives rich scope detail when available.
    status, body = _post(f"{_api_base(endpoint)}/apiTokens/lookup", token, {"token": token})
    if status == 200 and isinstance(body, dict):
        scopes = body.get("scopes", [])
        personal = body.get("personalAccessToken", False)
        can_ingest = INGEST_SCOPE in scopes and not personal
        if can_ingest:
            message = f"Ready — scope '{INGEST_SCOPE}' present."
        elif personal:
            message = ("Personal token: ingest scope can't be granted. "
                       "Add an admin-created regular API token.")
        else:
            message = f"Missing scope '{INGEST_SCOPE}'. Add it via an admin."
        return finish({
            "status": "healthy" if can_ingest else "needs_access",
            "healthy": can_ingest,
            "token": body.get("name"),
            "owner": body.get("owner"),
            "personal": personal,
            "scopes": scopes,
            "message": message,
        })

    # Step 2: introspection unavailable (e.g. an admin ingest-only token without
    # apiTokens.read, or a platform token). Probe the ingest endpoint directly.
    return finish(_probe_ingest(endpoint, token))


def main():
    print("=" * 64)
    print("Dynatrace readiness check")
    print("=" * 64)
    r = check_readiness()
    print(f"status   : {r['status'].upper()}")
    if r.get("token"):
        print(f"token    : {r['token']}  (owner: {r.get('owner', '?')})")
        print(f"type     : {'personal access token' if r.get('personal') else 'API token'}")
        print(f"scopes   : {', '.join(r.get('scopes') or []) or '(none)'}")
    print(f"ingest   : {'READY' if r['healthy'] else 'NOT READY'}")
    print(f"export   : {'ENABLED' if r.get('export_enabled') else 'disabled'}"
          f"{' — actively exporting' if r.get('exporting') else ''}")
    print(f"detail   : {r['message']}")


if __name__ == "__main__":
    main()
