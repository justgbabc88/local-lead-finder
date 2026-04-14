"""Redis + RQ wiring. One Redis connection, reused across the API and workers."""
from functools import lru_cache
from redis import Redis
from rq import Queue

from app.config import get_settings


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url)


@lru_cache
def get_scrape_queue() -> Queue:
    settings = get_settings()
    return Queue(
        settings.scrape_queue_name,
        connection=get_redis(),
        default_timeout=settings.worker_job_timeout,
    )


@lru_cache
def get_enrichment_queue() -> Queue:
    settings = get_settings()
    return Queue(
        settings.enrichment_queue_name,
        connection=get_redis(),
        default_timeout=settings.worker_job_timeout,
    )
