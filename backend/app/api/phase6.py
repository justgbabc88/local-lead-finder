"""Phase 6 endpoints: AI opener, templates, suppression list, territories,
notifications, niche benchmarks. (Scheduled scrapes + hygiene run as cron
workers — see app/workers/hygiene.py + scheduler.py.)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, require_user
from app.api.envelope import ok
from app.db.supabase_client import get_supabase
from app.services.ai_opener import AIOpenerError, generate_opener

router = APIRouter(tags=["phase6"])


# ========== 6a — AI Personalization ==========

class AIOpenerRequest(BaseModel):
    contact_id: str


@router.post("/api/ai/personalize")
async def personalize_opener(body: AIOpenerRequest, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    contact = sb.table("contacts").select("*").eq(
        "workspace_id", user.workspace_id,
    ).eq("id", body.contact_id).single().execute().data
    if not contact:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")

    company = sb.table("companies").select("*").eq(
        "id", contact["company_id"],
    ).single().execute().data
    if not company:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company missing")

    settings = sb.table("workspace_settings").select("anthropic_api_key").eq(
        "workspace_id", user.workspace_id,
    ).single().execute().data or {}

    try:
        opener = await generate_opener(
            api_key=settings.get("anthropic_api_key") or "",
            contact_name=contact.get("full_name") or contact.get("first_name") or "there",
            company_name=company.get("name") or "your business",
            category=company.get("primary_category"),
            rating=company.get("rating"),
            review_count=company.get("review_count"),
            website_snippet=(company.get("notes") or "")[:400] or None,
        )
    except AIOpenerError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))

    sb.table("contacts").update({"ai_opener": opener}).eq("id", body.contact_id).execute()
    return ok({"ai_opener": opener})


# ========== 6c — Saved Search Templates ==========

class TemplateCreate(BaseModel):
    name: str
    niche_keywords: list[str] = Field(default_factory=list)
    zip_codes: list[str] = Field(default_factory=list)
    filters: Optional[dict] = None
    schedule_cron: Optional[str] = None


@router.get("/api/templates")
async def list_templates(user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("search_templates").select("*").eq(
        "workspace_id", user.workspace_id,
    ).order("created_at", desc=True).execute()
    return ok(res.data or [])


@router.post("/api/templates", status_code=status.HTTP_201_CREATED)
async def create_template(body: TemplateCreate, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("search_templates").insert({
        "workspace_id": user.workspace_id,
        "name": body.name,
        "niche_keywords": body.niche_keywords,
        "zip_codes": body.zip_codes,
        "filters": body.filters,
        "schedule_cron": body.schedule_cron,
        "created_by": user.id,
    }).execute()
    return ok((res.data or [{}])[0])


@router.delete("/api/templates/{template_id}")
async def delete_template(template_id: str, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("search_templates").delete().eq(
        "workspace_id", user.workspace_id,
    ).eq("id", template_id).execute()
    return ok({"deleted": len(res.data or [])})


# ========== 6d — Suppression List ==========

class SuppressionItem(BaseModel):
    type: str = Field(..., pattern="^(email|domain)$")
    value: str
    reason: Optional[str] = None


class SuppressionBulk(BaseModel):
    items: list[SuppressionItem]


@router.get("/api/suppression")
async def list_suppression(user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("suppression_list").select("*").eq(
        "workspace_id", user.workspace_id,
    ).order("created_at", desc=True).limit(5000).execute()
    return ok(res.data or [])


@router.post("/api/suppression", status_code=status.HTTP_201_CREATED)
async def add_suppression(body: SuppressionBulk, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    rows = [{
        "workspace_id": user.workspace_id,
        "type": i.type,
        "value": i.value.lower().strip(),
        "reason": i.reason,
    } for i in body.items]
    # Ignore duplicates via on_conflict.
    sb.table("suppression_list").upsert(rows, on_conflict="workspace_id,type,value").execute()
    return ok({"added": len(rows)})


@router.delete("/api/suppression/{item_id}")
async def remove_suppression(item_id: str, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("suppression_list").delete().eq(
        "workspace_id", user.workspace_id,
    ).eq("id", item_id).execute()
    return ok({"deleted": len(res.data or [])})


# ========== 6f — Territories ==========

class TerritoryItem(BaseModel):
    zip_code: str
    assigned_to: Optional[str] = None
    label: Optional[str] = None


@router.get("/api/territories")
async def list_territories(user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("territories").select("*").eq(
        "workspace_id", user.workspace_id,
    ).execute()
    return ok(res.data or [])


@router.post("/api/territories", status_code=status.HTTP_201_CREATED)
async def upsert_territory(body: TerritoryItem, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("territories").upsert({
        "workspace_id": user.workspace_id,
        **body.model_dump(),
    }, on_conflict="workspace_id,zip_code").execute()
    return ok((res.data or [{}])[0])


@router.delete("/api/territories/{item_id}")
async def remove_territory(item_id: str, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("territories").delete().eq(
        "workspace_id", user.workspace_id,
    ).eq("id", item_id).execute()
    return ok({"deleted": len(res.data or [])})


# ========== 6g — Niche Performance Benchmarks ==========

@router.get("/api/benchmarks/niches")
async def niche_benchmarks(user: CurrentUser = Depends(require_user)):
    """Reply-rate leaderboard by niche keyword.

    Joins email_bison_exports → contacts → companies → niche_keyword to roll up
    reply rates. Without a campaign-level reply-rate feed we approximate using
    bison exports — full analytics integration lands when Bison exposes per-
    contact outcomes. For now returns push counts per niche as a placeholder.
    """
    sb = get_supabase()
    exports = sb.table("email_bison_exports").select(
        "contact_count, contact_ids, campaign_name"
    ).eq("workspace_id", user.workspace_id).execute().data or []

    # Map contact -> niche via their company's scrape_job.niche_keywords.
    all_contact_ids: list[str] = []
    for e in exports:
        all_contact_ids.extend(e.get("contact_ids") or [])
    if not all_contact_ids:
        return ok([])

    contacts = sb.table("contacts").select("id, company_id").in_(
        "id", all_contact_ids,
    ).execute().data or []
    company_ids = list({c["company_id"] for c in contacts if c.get("company_id")})
    companies = sb.table("companies").select("id, scrape_job_id").in_(
        "id", company_ids,
    ).execute().data or []
    company_to_job = {c["id"]: c.get("scrape_job_id") for c in companies}
    job_ids = list({j for j in company_to_job.values() if j})
    jobs = sb.table("scrape_jobs").select("id, niche_keywords").in_(
        "id", job_ids,
    ).execute().data or []
    job_to_niches = {j["id"]: j.get("niche_keywords") or [] for j in jobs}

    niche_totals: dict[str, int] = {}
    contact_to_company = {c["id"]: c["company_id"] for c in contacts}
    for e in exports:
        for cid in (e.get("contact_ids") or []):
            company_id = contact_to_company.get(cid)
            job_id = company_to_job.get(company_id or "")
            for niche in job_to_niches.get(job_id or "", []):
                niche_totals[niche] = niche_totals.get(niche, 0) + 1

    leaderboard = sorted(
        ({"niche": k, "pushed": v} for k, v in niche_totals.items()),
        key=lambda r: r["pushed"], reverse=True,
    )
    return ok(leaderboard)


# ========== 6h — Notifications ==========

@router.get("/api/notifications")
async def list_notifications(
    unread_only: bool = False, user: CurrentUser = Depends(require_user),
):
    sb = get_supabase()
    q = sb.table("notifications").select("*").eq("workspace_id", user.workspace_id)
    if unread_only:
        q = q.eq("is_read", False)
    res = q.order("created_at", desc=True).limit(50).execute()
    return ok(res.data or [])


@router.post("/api/notifications/{notif_id}/read")
async def mark_read(notif_id: str, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    sb.table("notifications").update({"is_read": True}).eq(
        "workspace_id", user.workspace_id,
    ).eq("id", notif_id).execute()
    return ok({"ok": True})


@router.post("/api/notifications/read-all")
async def mark_all_read(user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    sb.table("notifications").update({"is_read": True}).eq(
        "workspace_id", user.workspace_id,
    ).eq("is_read", False).execute()
    return ok({"ok": True})
