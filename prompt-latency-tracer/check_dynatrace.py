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
import ssl
import urllib.error
import urllib.request

from dotenv import load_dotenv

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


def _post(url: str, token: str, body: dict) -> tuple[int, dict | str]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Authorization": f"Api-Token {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except urllib.error.URLError as e:
        return 0, str(e)


def check_readiness() -> dict:
    """
    Returns a structured Dynatrace readiness verdict for the configured token.

    status is one of: healthy | needs_access | not_configured | error
    healthy=True only when trace ingest will actually work.
    """
    endpoint = os.getenv("DYNATRACE_ENDPOINT", "")
    token = os.getenv("DYNATRACE_API_TOKEN", "")

    if not endpoint or not token:
        return {
            "status": "not_configured",
            "healthy": False,
            "message": "Set DYNATRACE_ENDPOINT and DYNATRACE_API_TOKEN in .env",
        }

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
        return {
            "status": "healthy" if can_ingest else "needs_access",
            "healthy": can_ingest,
            "token": body.get("name"),
            "owner": body.get("owner"),
            "personal": personal,
            "scopes": scopes,
            "message": message,
        }
    if status == 401:
        return {"status": "error", "healthy": False,
                "message": "Token authentication failed (invalid/expired)."}
    if status == 403:
        return {"status": "error", "healthy": False,
                "message": "Token lacks apiTokens.read/write; cannot introspect."}
    if status == 0:
        return {"status": "error", "healthy": False, "message": f"Network error: {body}"}
    return {"status": "error", "healthy": False, "message": f"HTTP {status}: {body}"}


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
    print(f"detail   : {r['message']}")


if __name__ == "__main__":
    main()
