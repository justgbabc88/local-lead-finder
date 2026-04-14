"""Email validation endpoints."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, require_user
from app.api.envelope import ok
from app.config import get_settings
from app.db.supabase_client import get_supabase
from app.queue import get_enrichment_queue

# Batch size per worker task — validators fan out internally to 10 concurrent
# provider calls, so a batch of 50 is ~5s of wall time per worker.
BATCH = 50

router = APIRouter(prefix="/api/validation", tags=["validation"])


class ValidationJobCreate(BaseModel):
    contact_ids: list[str] = Field(..., min_length=1, max_length=50_000)


def _enqueue_batches(job_id: str, workspace_id: str, contact_ids: list[str]) -> int:
    queue = get_enrichment_queue()
    job_timeout = get_settings().worker_job_timeout
    count = 0
    for i in range(0, len(contact_ids), BATCH):
        batch = contact_ids[i:i + BATCH]
        queue.enqueue(
            "app.workers.validation_worker.run_validation_task",
            job_id, workspace_id, batch,
            job_timeout=job_timeout,
        )
        count += 1
    return count


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_validation_job(
    body: ValidationJobCreate,
    user: CurrentUser = Depends(require_user),
):
    sb = get_supabase()
    settings_res = sb.table("workspace_settings").select(
        "validation_provider, neverbounce_api_key, zerobounce_api_key,"
        " millionverifier_api_key, reoon_api_key"
    ).eq("workspace_id", user.workspace_id).single().execute()
    settings_row = settings_res.data or {}
    provider = settings_row.get("validation_provider") or "neverbounce"
    if not settings_row.get(f"{provider}_api_key"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Add a {provider} API key in Settings before validating.",
        )

    # Verify contacts belong to this workspace + have emails.
    ok_contacts = sb.table("contacts").select("id").eq(
        "workspace_id", user.workspace_id,
    ).in_("id", body.contact_ids).not_.is_("email", "null").execute()
    valid_ids = [r["id"] for r in (ok_contacts.data or [])]
    if not valid_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No contacts with emails in selection")

    job_res = sb.table("validation_jobs").insert({
        "workspace_id": user.workspace_id,
        "provider": provider,
        "contact_ids": valid_ids,
        "status": "running",
        "total_emails": len(valid_ids),
    }).execute()
    job = (job_res.data or [{}])[0]

    _enqueue_batches(job["id"], user.workspace_id, valid_ids)
    return ok(job)


@router.get("/jobs/{job_id}")
async def get_validation_job(job_id: str, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("validation_jobs").select("*").eq(
        "workspace_id", user.workspace_id,
    ).eq("id", job_id).single().execute()
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return ok(res.data)


@router.get("/jobs")
async def list_validation_jobs(limit: int = 20, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("validation_jobs").select("*").eq(
        "workspace_id", user.workspace_id,
    ).order("created_at", desc=True).limit(min(limit, 100)).execute()
    return ok(res.data or [])


@router.get("/summary")
async def validation_summary(user: CurrentUser = Depends(require_user)):
    """Dashboard counts: contacts by email_status."""
    sb = get_supabase()
    rows = sb.table("contacts").select("email_status").eq(
        "workspace_id", user.workspace_id,
    ).not_.is_("email", "null").execute()

    buckets: dict[str, int] = {}
    for r in (rows.data or []):
        s = r.get("email_status") or "unvalidated"
        buckets[s] = buckets.get(s, 0) + 1
    return ok(buckets)


@router.post("/restale")
async def revalidate_stale(user: CurrentUser = Depends(require_user)):
    """Find contacts whose validation is older than the workspace staleness window
    and enqueue a validation job for them."""
    sb = get_supabase()
    settings_res = sb.table("workspace_settings").select("validation_staleness_days").eq(
        "workspace_id", user.workspace_id,
    ).single().execute()
    days = (settings_res.data or {}).get("validation_staleness_days") or 90
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    rows = sb.table("contacts").select("id").eq(
        "workspace_id", user.workspace_id,
    ).not_.is_("email", "null").lt("validated_at", cutoff).execute()
    contact_ids = [r["id"] for r in (rows.data or [])]
    if not contact_ids:
        return ok({"queued": 0, "total": 0})

    provider = (sb.table("workspace_settings").select("validation_provider").eq(
        "workspace_id", user.workspace_id,
    ).single().execute().data or {}).get("validation_provider") or "neverbounce"

    job = sb.table("validation_jobs").insert({
        "workspace_id": user.workspace_id,
        "provider": provider,
        "contact_ids": contact_ids,
        "status": "running",
        "total_emails": len(contact_ids),
    }).execute().data[0]

    _enqueue_batches(job["id"], user.workspace_id, contact_ids)
    return ok({"queued": len(contact_ids), "total": len(contact_ids), "job_id": job["id"]})
