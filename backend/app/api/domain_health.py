"""Domain Health Monitor endpoints."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, require_user
from app.api.envelope import ok
from app.db.supabase_client import get_supabase
from app.queue import get_scrape_queue

router = APIRouter(prefix="/api/domain-health", tags=["domain-health"])


class DomainCreate(BaseModel):
    domain: str = Field(..., min_length=3)
    label: str | None = None
    dkim_selector: str | None = None
    check_frequency: str = "daily"
    alert_on_score_drop: bool = True
    alert_threshold: int = 70


class DomainUpdate(BaseModel):
    label: str | None = None
    dkim_selector: str | None = None
    alert_on_score_drop: bool | None = None
    alert_threshold: int | None = None
    is_active: bool | None = None


@router.get("")
async def list_domains(user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    rows = sb.table("monitored_domains").select("*").eq(
        "workspace_id", user.workspace_id,
    ).order("created_at", desc=True).execute().data or []

    # Attach latest check status per domain for list-view colors.
    if rows:
        ids = [r["id"] for r in rows]
        latest = sb.table("domain_health_checks").select(
            "domain_id, overall_status, spf_status, dkim_status, dmarc_status,"
            " mx_status, blacklist_status, checked_at",
        ).in_("domain_id", ids).order("checked_at", desc=True).execute().data or []
        by_domain: dict[str, dict] = {}
        for row in latest:
            by_domain.setdefault(row["domain_id"], row)
        for r in rows:
            r["latest_check"] = by_domain.get(r["id"])
    return ok(rows)


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_domain(
    body: DomainCreate,
    background: BackgroundTasks,
    user: CurrentUser = Depends(require_user),
):
    sb = get_supabase()
    clean_domain = body.domain.strip().lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").split("/")[0]
    payload = {
        "workspace_id": user.workspace_id,
        "domain": clean_domain,
        "label": body.label,
        "dkim_selector": body.dkim_selector,
        "check_frequency": body.check_frequency,
        "alert_on_score_drop": body.alert_on_score_drop,
        "alert_threshold": body.alert_threshold,
    }
    res = sb.table("monitored_domains").upsert(
        payload, on_conflict="workspace_id,domain",
    ).execute()
    if not res.data:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to add domain")
    domain = res.data[0]

    # Kick off an immediate first check — no waiting for the daily cron.
    try:
        get_scrape_queue().enqueue(
            "app.workers.domain_health_cron.run_all_health_checks",
            job_timeout=300,
        )
    except Exception:
        # Fall back: schedule in-process so the user sees a result on the dashboard.
        async def _one():
            from app.workers.domain_health_cron import _check_one as _c  # type: ignore
            await _c(domain)
        background.add_task(lambda: None)
    return ok(domain)


@router.delete("/{domain_id}")
async def remove_domain(domain_id: str, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("monitored_domains").delete().eq(
        "workspace_id", user.workspace_id,
    ).eq("id", domain_id).execute()
    return ok({"deleted": len(res.data or [])})


@router.patch("/{domain_id}")
async def update_domain(
    domain_id: str,
    body: DomainUpdate,
    user: CurrentUser = Depends(require_user),
):
    sb = get_supabase()
    fields = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    res = sb.table("monitored_domains").update(fields).eq(
        "workspace_id", user.workspace_id,
    ).eq("id", domain_id).execute()
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found")
    return ok(res.data[0])


@router.post("/{domain_id}/check")
async def manual_check(domain_id: str, user: CurrentUser = Depends(require_user)):
    """Trigger an immediate re-check of a domain."""
    sb = get_supabase()
    domain = sb.table("monitored_domains").select("*").eq(
        "workspace_id", user.workspace_id,
    ).eq("id", domain_id).single().execute().data
    if not domain:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found")

    # Enqueue the full batch runner; picking up just this one adds complexity
    # that's rarely useful (most workspaces monitor <10 domains).
    try:
        get_scrape_queue().enqueue(
            "app.workers.domain_health_cron.run_all_health_checks",
            job_timeout=300,
        )
        return ok({"queued": True})
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Redis unavailable: {e}")


@router.get("/{domain_id}/history")
async def history(domain_id: str, days: int = 30, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("domain_health_checks").select(
        "checked_at, overall_score, overall_status, issues_count",
    ).eq("workspace_id", user.workspace_id).eq(
        "domain_id", domain_id,
    ).order("checked_at", desc=True).limit(days).execute()
    return ok(res.data or [])


@router.get("/{domain_id}/history/latest")
async def latest(domain_id: str, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("domain_health_checks").select("*").eq(
        "workspace_id", user.workspace_id,
    ).eq("domain_id", domain_id).order("checked_at", desc=True).limit(1).execute()
    if not res.data:
        return ok(None)
    return ok(res.data[0])


@router.get("/alerts")
async def list_alerts(unresolved: bool = True, user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    q = sb.table("domain_health_alerts").select("*").eq("workspace_id", user.workspace_id)
    if unresolved:
        q = q.eq("is_resolved", False)
    res = q.order("alerted_at", desc=True).limit(100).execute()
    return ok(res.data or [])


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, user: CurrentUser = Depends(require_user)):
    from datetime import datetime, timezone
    sb = get_supabase()
    res = sb.table("domain_health_alerts").update({
        "is_resolved": True,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }).eq("workspace_id", user.workspace_id).eq("id", alert_id).execute()
    return ok({"resolved": len(res.data or [])})
