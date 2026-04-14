"""Scrape coordinator — fans a scrape_jobs row into N per-(zip, keyword) tasks.

Runs inside an RQ worker (not the API process) so the API stays fast no matter
how many zip × keyword combos a job has.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.db.supabase_client import get_supabase
from app.queue import get_scrape_queue

log = logging.getLogger(__name__)


def fan_out(job_id: str) -> None:
    """Enqueue one task per (zip_code, keyword) pair for the given job."""
    sb = get_supabase()
    settings = get_settings()

    job_res = sb.table("scrape_jobs").select("*").eq("id", job_id).single().execute()
    job = job_res.data
    if not job:
        log.error("coordinator: job %s not found", job_id)
        return

    workspace_id = job["workspace_id"]
    zips = job.get("zip_codes") or []
    keywords = job.get("niche_keywords") or []

    # Validate & pre-fetch zip centroids — drop unknown zips rather than fail the whole job.
    zres = sb.table("us_zip_codes").select("zip").in_("zip", zips).execute()
    known = {r["zip"] for r in (zres.data or [])}
    valid_zips = [z for z in zips if z in known]

    tasks = [(z, k) for z in valid_zips for k in keywords]
    total = len(tasks)

    sb.table("scrape_jobs").update({
        "status": "running",
        "total_tasks": total,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).execute()

    if total == 0:
        sb.table("scrape_jobs").update({
            "status": "error",
            "error_message": "No (zip, keyword) tasks to dispatch — check zips are seeded.",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", job_id).execute()
        return

    queue = get_scrape_queue()
    for zip_code, keyword in tasks:
        queue.enqueue(
            "app.workers.scrape_worker.run_scrape_task",
            workspace_id,
            job_id,
            zip_code,
            keyword,
            job_timeout=settings.worker_job_timeout,
            retry=None,  # Workers handle transient errors internally; no RQ-level retry.
        )

    log.info("coordinator: enqueued %d tasks for job %s", total, job_id)
