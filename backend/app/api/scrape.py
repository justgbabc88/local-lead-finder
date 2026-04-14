"""Scrape job endpoints."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, require_user
from app.api.envelope import ok
from app.config import get_settings
from app.db.supabase_client import get_supabase
from app.models.schemas import CompanyDetailsRequest, ScrapeJobCreate
from app.queue import get_scrape_queue
from app.services.scraper import fetch_details_for_companies, run_scrape_job

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scrape", tags=["scrape"])


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_scrape_job(
    body: ScrapeJobCreate,
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

    # Phase 2: enqueue the coordinator, which fans tasks into the scrape queue.
    # If Redis is unreachable, fall back to the in-process sync runner so Phase 1
    # setups keep working without Redis configured.
    settings = get_settings()
    try:
        get_scrape_queue().enqueue(
            "app.workers.coordinator.fan_out",
            job["id"],
            job_timeout=settings.worker_job_timeout,
        )
    except Exception as e:  # pragma: no cover
        log.warning("Redis unavailable, falling back to in-process scrape: %s", e)
        import asyncio
        asyncio.create_task(run_scrape_job(job["id"]))

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
