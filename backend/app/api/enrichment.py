"""Enrichment job endpoints — Apollo + CompanyEnrich (manual trigger)."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, require_user
from app.api.envelope import ok
from app.config import get_settings
from app.db.supabase_client import get_supabase
from app.queue import get_enrichment_queue

router = APIRouter(prefix="/api/enrichment", tags=["enrichment"])


class EnrichmentJobCreate(BaseModel):
    provider: Literal["apollo", "companyenrich"]
    company_ids: list[str] = Field(..., min_length=1, max_length=5000)


class EnrichmentRunRequest(BaseModel):
    confirmed: bool = True


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_enrichment_job(
    body: EnrichmentJobCreate,
    user: CurrentUser = Depends(require_user),
):
    """Create (but don't run) an enrichment job. Returns the job + credit estimate."""
    sb = get_supabase()

    # Verify all companies belong to this workspace.
    check = sb.table("companies").select("id").eq(
        "workspace_id", user.workspace_id
    ).in_("id", body.company_ids).execute()
    valid_ids = [r["id"] for r in (check.data or [])]
    if len(valid_ids) != len(body.company_ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Some company IDs are not in your workspace")

    # Rough credit estimate: 1 per company for org enrich + up to N for people.
    settings_res = sb.table("workspace_settings").select("default_contact_cap").eq(
        "workspace_id", user.workspace_id
    ).single().execute()
    cap = (settings_res.data or {}).get("default_contact_cap") or 3
    estimated_credits = len(valid_ids) * (1 + cap if body.provider == "apollo" else 1)

    res = sb.table("enrichment_jobs").insert({
        "workspace_id": user.workspace_id,
        "provider": body.provider,
        "company_ids": valid_ids,
        "status": "queued",
        "total_records": len(valid_ids),
        "estimated_credits": estimated_credits,
        "created_by": user.id,
    }).execute()
    if not res.data:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create enrichment job")
    return ok(res.data[0])


@router.post("/jobs/{job_id}/run")
async def run_enrichment_job(
    job_id: str,
    _: EnrichmentRunRequest = EnrichmentRunRequest(),
    user: CurrentUser = Depends(require_user),
):
    """Start a queued enrichment job (explicit confirm step after the cost estimate)."""
    sb = get_supabase()
    job_res = sb.table("enrichment_jobs").select("*").eq(
        "workspace_id", user.workspace_id
    ).eq("id", job_id).single().execute()
    job = job_res.data
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if job["status"] != "queued":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Job is {job['status']}")

    sb.table("enrichment_jobs").update({
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).execute()

    settings = get_settings()
    queue = get_enrichment_queue()
    for company_id in job["company_ids"]:
        queue.enqueue(
            "app.workers.enrichment_worker.run_enrichment_task",
            job_id,
            user.workspace_id,
            company_id,
            job["provider"],
            job_timeout=settings.worker_job_timeout,
        )
    return ok({"queued": len(job["company_ids"])})


@router.get("/jobs/{job_id}")
async def get_enrichment_job(job_id: str, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("enrichment_jobs").select("*").eq(
        "workspace_id", user.workspace_id
    ).eq("id", job_id).single().execute()
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return ok(res.data)


@router.get("/jobs")
async def list_enrichment_jobs(limit: int = 20, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("enrichment_jobs").select("*").eq(
        "workspace_id", user.workspace_id
    ).order("created_at", desc=True).limit(min(limit, 100)).execute()
    return ok(res.data or [])


@router.post("/jobs/{job_id}/cancel")
async def cancel_enrichment_job(job_id: str, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("enrichment_jobs").update({
        "status": "cancelled",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("workspace_id", user.workspace_id).eq("id", job_id).in_(
        "status", ["queued", "running"],
    ).execute()
    return ok({"cancelled": len(res.data or []) > 0})
