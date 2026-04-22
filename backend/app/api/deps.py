"""Shared FastAPI dependencies: auth, workspace resolution."""
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional
import jwt
from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings
from app.db.supabase_client import get_supabase


@dataclass
class AuthedUser:
    """Caller authenticated via Supabase JWT (no workspace required)."""
    id: str
    email: Optional[str]


@dataclass
class CurrentUser(AuthedUser):
    """Authed user with a resolved workspace membership."""
    workspace_id: str
    role: str


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    settings = get_settings()
    return jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")


def _decode_jwt(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        alg = jwt.get_unverified_header(token).get("alg", "HS256")
        if alg == "HS256":
            key: Any = settings.supabase_jwt_secret
        else:
            key = _jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=[alg], audience="authenticated")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}")


async def require_auth(
    authorization: str = Header(..., alias="Authorization"),
) -> AuthedUser:
    """JWT-only auth. Use this for endpoints that don't need a workspace (e.g. bootstrap)."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    claims = _decode_jwt(token)
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token")
    return AuthedUser(id=user_id, email=claims.get("email"))


async def require_user(
    auth: AuthedUser = Depends(require_auth),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
) -> CurrentUser:
    """Auth + workspace membership. Clients pick the active workspace via X-Workspace-Id."""
    sb = get_supabase()
    q = sb.table("workspace_members").select("workspace_id, role").eq("user_id", auth.id)
    if x_workspace_id:
        q = q.eq("workspace_id", x_workspace_id)
    res = q.limit(1).execute()
    if not res.data:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Not a member of this workspace" if x_workspace_id else "User has no workspace membership",
        )
    row = res.data[0]
    return CurrentUser(
        id=auth.id,
        email=auth.email,
        workspace_id=row["workspace_id"],
        role=row.get("role", "member"),
    )
