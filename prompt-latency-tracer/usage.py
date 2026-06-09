# usage.py
"""
Tracks Google API request usage per key per day so the app can warn when a key
is close to (or has hit) the free-tier daily request quota. Google doesn't
expose remaining quota via API, so we count requests locally in usage.json.
"""
import json
import os
from datetime import date
from pathlib import Path

USAGE_FILE = Path(__file__).resolve().parent / "usage.json"

# Free-tier requests/day per key (gemini-2.5-flash ≈ 20). Configurable via env.
FREE_TIER_RPD = int(os.getenv("GOOGLE_FREE_TIER_RPD", "20"))
LOW_THRESHOLD = int(os.getenv("GOOGLE_LOW_THRESHOLD", "5"))


def _fingerprint(key: str) -> str:
    """A short, non-secret id for a key (used as a stable dict key)."""
    return f"{key[:6]}…{key[-4:]}" if len(key) > 12 else key


def _load() -> dict:
    try:
        data = json.loads(USAGE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    today = date.today().isoformat()
    if data.get("date") != today:  # reset daily
        data = {"date": today, "counts": {}, "exhausted": {}}
    data.setdefault("counts", {})
    data.setdefault("exhausted", {})
    return data


def _save(data: dict) -> None:
    USAGE_FILE.write_text(json.dumps(data))


def record_request(key: str) -> None:
    data = _load()
    fp = _fingerprint(key)
    data["counts"][fp] = data["counts"].get(fp, 0) + 1
    _save(data)


def mark_exhausted(key: str) -> None:
    data = _load()
    data["exhausted"][_fingerprint(key)] = True
    _save(data)


def status(keys: list[str]) -> dict:
    """Return per-key and aggregate quota status for the health endpoint."""
    data = _load()
    out = []
    remaining_total = 0
    for i, k in enumerate(keys):
        fp = _fingerprint(k)
        used = data["counts"].get(fp, 0)
        exhausted = bool(data["exhausted"].get(fp, False))
        remaining = 0 if exhausted else max(0, FREE_TIER_RPD - used)
        remaining_total += remaining
        out.append({
            "id": f"key{i + 1}",
            "fingerprint": fp,
            "used": used,
            "limit": FREE_TIER_RPD,
            "remaining": remaining,
            "exhausted": exhausted,
        })
    warning = remaining_total <= LOW_THRESHOLD or any(o["exhausted"] for o in out)
    return {
        "keys": out,
        "remaining_total": remaining_total,
        "limit_per_key": FREE_TIER_RPD,
        "low_threshold": LOW_THRESHOLD,
        "warning": warning,
    }
