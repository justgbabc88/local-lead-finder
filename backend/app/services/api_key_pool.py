"""API key pool operations backed by Postgres RPC.

Atomically picks the least-used active key for a workspace and increments its
counter in a single call (FOR UPDATE SKIP LOCKED). Workers also flag keys as
`rate-limited` when they hit 429, which removes them from the pool until the
daily reset restores them.
"""
from dataclasses import dataclass
from typing import Optional

from app.config import get_settings
from app.db.supabase_client import get_supabase


@dataclass
class CheckedOutKey:
    id: str
    key_value: str


def checkout(workspace_id: str) -> Optional[CheckedOutKey]:
    """Return a key ready to use, or None if no key has remaining quota.

    Falls back to the env GOOGLE_PLACES_API_KEY if the pool is empty — useful for
    dev, but in prod the pool should always have entries.
    """
    sb = get_supabase()
    res = sb.rpc("checkout_google_api_key", {"ws": workspace_id}).execute()
    rows = res.data or []
    if rows:
        row = rows[0]
        return CheckedOutKey(id=row["id"], key_value=row["key_value"])

    fallback = get_settings().google_places_api_key
    if fallback:
        return CheckedOutKey(id="env_fallback", key_value=fallback)
    return None


def flag(workspace_id: str, key_id: str, *, status: str, error: str) -> None:
    """Mark a pool key as rate-limited / error. No-op for the env fallback."""
    if key_id == "env_fallback":
        return
    get_supabase().rpc(
        "flag_google_api_key",
        {"ws": workspace_id, "key_id": key_id, "new_status": status, "err": error},
    ).execute()


def reset_daily_counters() -> int:
    """Reset every pool key's calls_today to 0. Called daily via rq-scheduler."""
    res = get_supabase().rpc("reset_google_api_key_counters").execute()
    return int(res.data or 0)
