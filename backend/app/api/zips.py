"""US zip code lookup endpoints (public read for authenticated users)."""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthedUser, require_auth
from app.api.envelope import ok
from app.db.supabase_client import get_supabase

router = APIRouter(prefix="/api/zips", tags=["zips"])


@router.get("")
async def search_zips(
    state: Optional[str] = Query(None, description="2-letter state abbreviation"),
    city: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
    _: AuthedUser = Depends(require_auth),
):
    sb = get_supabase()
    q = sb.table("us_zip_codes").select("zip,city,state_abbr,lat,lng,population")
    if state:
        q = q.eq("state_abbr", state.upper())
    if city:
        q = q.ilike("city", f"%{city}%")
    res = q.order("zip").limit(limit).execute()
    return ok(res.data or [])
