"""Workspace settings + Google API key pool endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, require_user
from app.api.envelope import ok
from app.db.supabase_client import get_supabase
from app.models.schemas import GoogleApiKeyCreate, WorkspaceSettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ---------- Workspace settings ----------

_SECRET_FIELDS = {
    "apollo_api_key", "companyenrich_api_key", "email_bison_api_key",
    "neverbounce_api_key", "zerobounce_api_key", "millionverifier_api_key",
    "reoon_api_key", "anthropic_api_key", "mxtoolbox_api_key",
}


def _redact(settings: dict) -> dict:
    """Never return secret values over the wire — expose a boolean `<field>_set` instead."""
    out = dict(settings)
    for k in _SECRET_FIELDS:
        if k in out:
            out[f"{k}_set"] = bool(out.pop(k))
    return out


@router.get("")
async def get_settings_(user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("workspace_settings").select("*").eq(
        "workspace_id", user.workspace_id
    ).limit(1).execute()
    return ok(_redact(res.data[0]) if res.data else {"workspace_id": user.workspace_id})


@router.patch("")
async def update_settings(
    body: WorkspaceSettingsUpdate,
    user: CurrentUser = Depends(require_user),
):
    sb = get_supabase()
    fields = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    fields["workspace_id"] = user.workspace_id
    res = sb.table("workspace_settings").upsert(fields, on_conflict="workspace_id").execute()
    return ok(_redact(res.data[0]) if res.data else {})


# ---------- Google API key pool ----------

@router.get("/google-keys")
async def list_google_keys(user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("api_keys_google").select(
        "id,name,daily_quota,calls_today,status,last_used_at,last_error,created_at"
    ).eq("workspace_id", user.workspace_id).order("created_at").execute()
    return ok(res.data or [])


@router.post("/google-keys", status_code=status.HTTP_201_CREATED)
async def add_google_key(
    body: GoogleApiKeyCreate,
    user: CurrentUser = Depends(require_user),
):
    sb = get_supabase()
    res = sb.table("api_keys_google").insert({
        "workspace_id": user.workspace_id,
        "name": body.name,
        "key_value": body.key_value,
        "daily_quota": body.daily_quota,
    }).execute()
    if not res.data:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to add key")
    row = dict(res.data[0])
    row.pop("key_value", None)
    return ok(row)


@router.delete("/google-keys/{key_id}")
async def delete_google_key(key_id: str, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("api_keys_google").delete().eq(
        "workspace_id", user.workspace_id
    ).eq("id", key_id).execute()
    return ok({"deleted": len(res.data or [])})


@router.post("/google-keys/{key_id}/reset")
async def reset_google_key_counter(key_id: str, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("api_keys_google").update({
        "calls_today": 0, "status": "active", "last_error": None,
    }).eq("workspace_id", user.workspace_id).eq("id", key_id).execute()
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Key not found")
    return ok({"reset": True})
