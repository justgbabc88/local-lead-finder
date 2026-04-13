"""Workspace bootstrap + listing endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import AuthedUser, CurrentUser, require_auth, require_user
from app.api.envelope import ok
from app.db.supabase_client import get_supabase
from app.models.schemas import WorkspaceCreate

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("")
async def list_my_workspaces(auth: AuthedUser = Depends(require_auth)):
    sb = get_supabase()
    mems = sb.table("workspace_members").select("workspace_id, role").eq(
        "user_id", auth.id
    ).execute()
    if not mems.data:
        return ok([])

    ids = [m["workspace_id"] for m in mems.data]
    ws = sb.table("workspaces").select("*").in_("id", ids).execute()
    role_by_id = {m["workspace_id"]: m.get("role") for m in mems.data}
    result = [{**w, "role": role_by_id.get(w["id"])} for w in (ws.data or [])]
    return ok(result)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_workspace(
    body: WorkspaceCreate,
    auth: AuthedUser = Depends(require_auth),
):
    """Create a workspace, add the caller as owner, seed workspace_settings."""
    sb = get_supabase()
    ws_res = sb.table("workspaces").insert({
        "name": body.name,
        "owner_id": auth.id,
    }).execute()
    if not ws_res.data:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Workspace creation failed")
    ws = ws_res.data[0]

    sb.table("workspace_members").insert({
        "workspace_id": ws["id"],
        "user_id": auth.id,
        "role": "owner",
    }).execute()

    sb.table("workspace_settings").insert({"workspace_id": ws["id"]}).execute()

    return ok({**ws, "role": "owner"})


@router.get("/me")
async def current_workspace(user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("workspaces").select("*").eq("id", user.workspace_id).single().execute()
    return ok({**(res.data or {}), "role": user.role})
