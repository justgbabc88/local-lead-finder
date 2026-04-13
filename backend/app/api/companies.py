"""Company + contact endpoints."""
import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, require_user
from app.api.envelope import ok
from app.db.supabase_client import get_supabase
from app.models.schemas import CompanyUpdate

router = APIRouter(prefix="/api/companies", tags=["companies"])


def _apply_filters(q, *, state: Optional[str], zip: Optional[str],
                   city: Optional[str], min_rating: Optional[float],
                   min_reviews: Optional[int], category: Optional[str],
                   is_archived: Optional[bool], search: Optional[str]):
    if state:
        q = q.eq("state", state.upper())
    if zip:
        q = q.eq("zip", zip)
    if city:
        q = q.ilike("city", f"%{city}%")
    if min_rating is not None:
        q = q.gte("rating", min_rating)
    if min_reviews is not None:
        q = q.gte("review_count", min_reviews)
    if category:
        q = q.ilike("primary_category", f"%{category}%")
    if is_archived is not None:
        q = q.eq("is_archived", is_archived)
    if search:
        q = q.ilike("name", f"%{search}%")
    return q


@router.get("")
async def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    state: Optional[str] = None,
    zip: Optional[str] = None,
    city: Optional[str] = None,
    min_rating: Optional[float] = None,
    min_reviews: Optional[int] = None,
    category: Optional[str] = None,
    is_archived: Optional[bool] = False,
    search: Optional[str] = None,
    user: CurrentUser = Depends(require_user),
):
    sb = get_supabase()
    start = (page - 1) * page_size
    end = start + page_size - 1

    q = sb.table("companies").select("*", count="exact").eq("workspace_id", user.workspace_id)
    q = _apply_filters(q, state=state, zip=zip, city=city, min_rating=min_rating,
                       min_reviews=min_reviews, category=category,
                       is_archived=is_archived, search=search)
    res = q.order("created_at", desc=True).range(start, end).execute()

    rows = res.data or []
    # contact counts in one round-trip
    if rows:
        ids = [r["id"] for r in rows]
        counts_res = sb.table("contacts").select("company_id", count="exact").in_(
            "company_id", ids
        ).execute()
        # supabase-py doesn't return per-group counts; do it manually
        counts: dict[str, int] = {}
        for c in counts_res.data or []:
            counts[c["company_id"]] = counts.get(c["company_id"], 0) + 1
        for r in rows:
            r["contact_count"] = counts.get(r["id"], 0)

    return ok(rows, meta={"page": page, "page_size": page_size, "total": res.count})


@router.get("/export")
async def export_companies_csv(
    state: Optional[str] = None,
    zip: Optional[str] = None,
    city: Optional[str] = None,
    min_rating: Optional[float] = None,
    min_reviews: Optional[int] = None,
    category: Optional[str] = None,
    is_archived: Optional[bool] = False,
    search: Optional[str] = None,
    user: CurrentUser = Depends(require_user),
):
    sb = get_supabase()
    q = sb.table("companies").select("*").eq("workspace_id", user.workspace_id)
    q = _apply_filters(q, state=state, zip=zip, city=city, min_rating=min_rating,
                       min_reviews=min_reviews, category=category,
                       is_archived=is_archived, search=search)
    # Cap export at 10k rows for Phase 1.
    res = q.order("name").limit(10000).execute()
    rows = res.data or []

    fields = [
        "name", "address", "city", "state", "zip", "phone", "website",
        "rating", "review_count", "primary_category", "business_status",
        "google_maps_url", "apollo_enriched_at", "companyenrich_enriched_at",
        "lead_score", "tags",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        row = {k: r.get(k) for k in fields}
        if isinstance(row.get("tags"), list):
            row["tags"] = ";".join(row["tags"])
        writer.writerow(row)
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=companies.csv"},
    )


@router.get("/{company_id}")
async def get_company(company_id: str, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("companies").select("*").eq(
        "workspace_id", user.workspace_id
    ).eq("id", company_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")

    contacts_res = sb.table("contacts").select("*").eq(
        "company_id", company_id
    ).order("is_primary", desc=True).execute()

    return ok({**res.data[0], "contacts": contacts_res.data or []})


@router.patch("/{company_id}")
async def update_company(
    company_id: str,
    body: CompanyUpdate,
    user: CurrentUser = Depends(require_user),
):
    sb = get_supabase()
    fields = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    res = sb.table("companies").update(fields).eq(
        "workspace_id", user.workspace_id
    ).eq("id", company_id).execute()
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    return ok(res.data[0])


@router.delete("/{company_id}")
async def soft_delete_company(company_id: str, user: CurrentUser = Depends(require_user)):
    """Soft delete: set is_archived=true (never hard delete lead data)."""
    sb = get_supabase()
    res = sb.table("companies").update({"is_archived": True}).eq(
        "workspace_id", user.workspace_id
    ).eq("id", company_id).execute()
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    return ok({"archived": True})
