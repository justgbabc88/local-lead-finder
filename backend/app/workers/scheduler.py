"""rq-scheduler entrypoint — schedules the daily API key counter reset.

Run alongside the workers as a separate process:
    rqscheduler --url $REDIS_URL -i 60

Once started, this script registers the reset job (idempotent). Safe to re-run.
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timezone

from rq_scheduler import Scheduler

from app.queue import get_redis

log = logging.getLogger(__name__)

DAILY_RESET_ID = "daily_api_key_reset"


def _midnight_utc_today() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime.combine(now.date(), time.min, tzinfo=timezone.utc)


def register_schedules() -> None:
    scheduler = Scheduler(connection=get_redis())

    # Cancel any previous registration so we never end up with duplicates.
    for job in scheduler.get_jobs():
        if job.meta.get("lle_id") == DAILY_RESET_ID:
            scheduler.cancel(job)

    job = scheduler.cron(
        cron_string="0 0 * * *",  # every day at 00:00 UTC
        func="app.services.api_key_pool.reset_daily_counters",
        repeat=None,
        queue_name="scrape_tasks",
        meta={"lle_id": DAILY_RESET_ID},
    )
    log.info("Registered daily API key reset as job %s", job.id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    register_schedules()
