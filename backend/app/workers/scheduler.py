"""rq-scheduler entrypoint — registers recurring jobs. Idempotent.

Run alongside the workers as a separate process:
    python -m app.workers.scheduler && rqscheduler --url $REDIS_URL -i 60
"""
from __future__ import annotations

import logging

from rq_scheduler import Scheduler

from app.queue import get_redis

log = logging.getLogger(__name__)

SCHEDULED_JOBS = [
    ("daily_api_key_reset", "0 0 * * *",
     "app.services.api_key_pool.reset_daily_counters", "scrape_tasks"),
    ("hourly_scheduled_scrapes", "*/15 * * * *",
     "app.workers.scheduled_scrapes.dispatch_scheduled_scrapes", "scrape_tasks"),
    ("nightly_hygiene", "30 3 * * *",
     "app.workers.hygiene.run_hygiene", "scrape_tasks"),
    ("daily_domain_health", "0 6 * * *",
     "app.workers.domain_health_cron.run_all_health_checks", "scrape_tasks"),
]


def register_schedules() -> None:
    scheduler = Scheduler(connection=get_redis())

    # Clear previously-registered LLE cron jobs (meta.lle_id lets us find them).
    for job in scheduler.get_jobs():
        if job.meta.get("lle_id"):
            scheduler.cancel(job)

    for lle_id, cron_expr, func, queue in SCHEDULED_JOBS:
        job = scheduler.cron(
            cron_string=cron_expr,
            func=func,
            repeat=None,
            queue_name=queue,
            meta={"lle_id": lle_id},
        )
        log.info("Registered %s as %s (%s)", lle_id, job.id, cron_expr)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    register_schedules()
