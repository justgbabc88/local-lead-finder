"""Nightly data hygiene.

- Tags companies with 0 contacts and no enrichment after 48h as `needs_enrichment`.
- Archives companies marked CLOSED_PERMANENTLY for 30+ days.
- Logs every action to hygiene_log.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.supabase_client import get_supabase


def _log(workspace_id: str, action: str, company_id: str, details: dict | None = None) -> None:
    get_supabase().table("hygiene_log").insert({
        "workspace_id": workspace_id,
        "action": action,
        "company_id": company_id,
        "details": details,
    }).execute()


def run_hygiene() -> dict:
    sb = get_supabase()
    now = datetime.now(timezone.utc)
    flagged = archived = 0

    two_days_ago = (now - timedelta(hours=48)).isoformat()
    stale = sb.table("companies").select("id, workspace_id, tags").lt(
        "created_at", two_days_ago,
    ).is_("apollo_enriched_at", "null").is_(
        "companyenrich_enriched_at", "null",
    ).eq("is_archived", False).execute().data or []

    for c in stale:
        # Check contact count per company.
        cnt = sb.table("contacts").select("id", count="exact").eq(
            "company_id", c["id"],
        ).limit(1).execute()
        if (cnt.count or 0) > 0:
            continue
        tags = set(c.get("tags") or [])
        if "needs_enrichment" in tags:
            continue
        tags.add("needs_enrichment")
        sb.table("companies").update({"tags": list(tags)}).eq("id", c["id"]).execute()
        _log(c["workspace_id"], "flag_needs_enrichment", c["id"])
        flagged += 1

    month_ago = (now - timedelta(days=30)).isoformat()
    closed = sb.table("companies").select("id, workspace_id").eq(
        "business_status", "CLOSED_PERMANENTLY",
    ).eq("is_archived", False).lt("updated_at", month_ago).execute().data or []
    for c in closed:
        sb.table("companies").update({"is_archived": True}).eq("id", c["id"]).execute()
        _log(c["workspace_id"], "archive_closed", c["id"])
        archived += 1

    return {"flagged": flagged, "archived": archived}


if __name__ == "__main__":
    print(run_hygiene())
