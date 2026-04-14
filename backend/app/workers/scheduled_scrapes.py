"""Scheduled scrape runner (6e).

Runs every hour; re-creates a scrape_job from any search_template whose
schedule_cron matches the current time. We use a simple DOW/HH/MM matcher
rather than full cron — good enough for 'daily at N' patterns.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.db.supabase_client import get_supabase
from app.queue import get_scrape_queue
from app.services.notify import notify

log = logging.getLogger(__name__)


def _cron_matches(expr: str, now: datetime) -> bool:
    """Minimal 5-field cron: minute hour dom month dow. Supports *, commas, and ints."""
    parts = expr.strip().split()
    if len(parts) != 5:
        return False
    def ok(field: str, value: int) -> bool:
        if field == "*":
            return True
        for token in field.split(","):
            if token == "*":
                return True
            try:
                if int(token) == value:
                    return True
            except ValueError:
                return False
        return False
    return (
        ok(parts[0], now.minute)
        and ok(parts[1], now.hour)
        and ok(parts[2], now.day)
        and ok(parts[3], now.month)
        and ok(parts[4], now.weekday())
    )


def dispatch_scheduled_scrapes() -> int:
    sb = get_supabase()
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    templates = sb.table("search_templates").select("*").not_.is_(
        "schedule_cron", "null",
    ).execute().data or []

    count = 0
    for t in templates:
        if not _cron_matches(t["schedule_cron"], now):
            continue
        payload = {
            "workspace_id": t["workspace_id"],
            "status": "queued",
            "niche_keywords": t.get("niche_keywords") or [],
            "zip_codes": t.get("zip_codes") or [],
            "radius_miles": (t.get("filters") or {}).get("radius_miles") or 10,
            "min_rating": (t.get("filters") or {}).get("min_rating"),
            "min_reviews": (t.get("filters") or {}).get("min_reviews"),
            "exclude_chains": (t.get("filters") or {}).get("exclude_chains") or False,
            "two_pass_mode": (t.get("filters") or {}).get("two_pass_mode", True),
            "worker_count": (t.get("filters") or {}).get("worker_count") or 10,
            "total_tasks": len(t.get("niche_keywords") or []) * len(t.get("zip_codes") or []),
            "created_by": t.get("created_by"),
        }
        if payload["total_tasks"] == 0:
            continue
        job = sb.table("scrape_jobs").insert(payload).execute().data[0]
        get_scrape_queue().enqueue("app.workers.coordinator.fan_out", job["id"])
        notify(
            workspace_id=t["workspace_id"],
            type="scheduled_scrape",
            title=f"Scheduled scrape started: {t['name']}",
            body=f"{payload['total_tasks']} tasks queued from template {t['name']}.",
            link="/scrape",
        )
        count += 1
    return count
