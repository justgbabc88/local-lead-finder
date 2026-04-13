"""Scrape job endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api.deps import CurrentUser, require_user
from app.api.envelope import ok
from app.db.supabase_client import get_supabase
from app.models.schemas import CompanyDetailsRequest, ScrapeJobCreate
from app.services.scraper import fetch_details_for_companies, run_scrape_job

router = APIRouter(prefix="/api/scrape", tags=["scrape"])


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_scrape_job(
    body: ScrapeJobCreate,
    background: BackgroundTasks,
    user: CurrentUser = Depends(require_user),
):
    sb = get_supabase()

    # Basic sanity: validate zip codes exist in us_zip_codes
    known = sb.table("us_zip_codes").select("zip").in_("zip", body.zip_codes).execute()
    known_set = {r["zip"] for r in (known.data or [])}
    missing = [z for z in body.zip_codes if z not in known_set]
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unknown zip codes (run seed_zips?): {missing[:10]}",
        )

    payload = {
        "workspace_id": user.workspace_id,
        "status": "queued",
        "niche_keywords": body.niche_keywords,
        "zip_codes": body.zip_codes,
        "radius_miles": body.radius_miles,
        "min_rating": body.min_rating,
        "min_reviews": body.min_reviews,
        "exclude_chains": body.exclude_chains,
        "two_pass_mode": body.two_pass_mode,
        "worker_count": body.worker_count,
        "total_tasks": len(body.niche_keywords) * len(body.zip_codes),
        "created_by": user.id,
    }
    res = sb.table("scrape_jobs").insert(payload).execute()
    if not res.data:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create job")
    job = res.data[0]

    # Phase 1: run synchronously in-process as a FastAPI background task.
    # Phase 2 will swap this for a Redis queue + parallel Railway workers.
    background.add_task(run_scrape_job, job["id"])

    return ok(job)


@router.get("/jobs")
async def list_scrape_jobs(
    limit: int = 20,
    user: CurrentUser = Depends(require_user),
):
    sb = get_supabase()
    res = sb.table("scrape_jobs").select("*").eq(
        "workspace_id", user.workspace_id
    ).order("created_at", desc=True).limit(min(limit, 100)).execute()
    return ok(res.data or [])


@router.get("/jobs/{job_id}")
async def get_scrape_job(job_id: str, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("scrape_jobs").select("*").eq(
        "workspace_id", user.workspace_id
    ).eq("id", job_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return ok(res.data[0])


@router.post("/jobs/{job_id}/cancel")
async def cancel_scrape_job(job_id: str, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    # The running task checks status between tasks — setting cancelled won't interrupt
    # an in-flight Google call, but will stop after the current task completes.
    # Phase 2 workers will check a Redis flag for faster cancellation.
    res = sb.table("scrape_jobs").update({
        "status": "cancelled",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("workspace_id", user.workspace_id).eq("id", job_id).in_(
        "status", ["queued", "running"]
    ).execute()
    return ok({"cancelled": len(res.data or []) > 0})


@router.post("/fetch-details")
async def fetch_details(
    body: CompanyDetailsRequest,
    user: CurrentUser = Depends(require_user),
):
    """Pass 2: fetch Place Details for a list of companies already in the DB."""
    updated = await fetch_details_for_companies(user.workspace_id, body.company_ids)
    return ok({"updated": updated})
