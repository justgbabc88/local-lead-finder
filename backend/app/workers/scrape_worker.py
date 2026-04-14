"""Per-(zip, keyword) scrape task. Runs inside an RQ worker.

Each task:
  1. Checks a zip centroid from us_zip_codes.
  2. Checks out a Google Places API key from the workspace pool (atomic RPC).
  3. Runs Text Search + optional Place Details.
  4. Upserts matching companies (workspace_id + place_id is the dedup key).
  5. Atomically bumps job counters — the RPC flips the job to 'complete' when
     the last task finishes.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from app.db.supabase_client import get_supabase
from app.services import api_key_pool
from app.services.google_places import (
    GooglePlacesClient,
    GooglePlacesError,
    normalize_place,
)

log = logging.getLogger(__name__)

_CHAIN_HINTS = {
    "mcdonald", "starbucks", "subway", "walmart", "target", "costco",
    "home depot", "lowe's", "lowes", "cvs", "walgreens", "rite aid",
    "7-eleven", "chase", "wells fargo", "bank of america",
}


def _miles_to_meters(miles: int) -> int:
    return int(miles * 1609.34)


def _is_chain(name: str) -> bool:
    n = (name or "").lower()
    return any(hint in n for hint in _CHAIN_HINTS)


def _bump_counters(
    job_id: str, *, completed: int, failed: int, records_found: int, api_calls: int
) -> None:
    res = get_supabase().rpc(
        "bump_scrape_job_counters",
        {
            "p_job_id": job_id,
            "p_completed": completed,
            "p_failed": failed,
            "p_records_found": records_found,
            "p_api_calls": api_calls,
        },
    ).execute()

    # On the transition to 'complete', fire an in-app + Slack notification.
    rows = res.data or []
    if rows and rows[0].get("status") == "complete":
        try:
            from app.services.notify import notify
            job = get_supabase().table("scrape_jobs").select(
                "workspace_id, records_found, niche_keywords, zip_codes"
            ).eq("id", job_id).single().execute().data or {}
            notify(
                workspace_id=job["workspace_id"],
                type="scrape_complete",
                title=f"Scrape complete — {job.get('records_found', 0)} leads",
                body=f"{len(job.get('niche_keywords') or [])} keyword(s) × "
                     f"{len(job.get('zip_codes') or [])} zips.",
                link="/leads",
            )
        except Exception as e:  # pragma: no cover
            log.warning("finalize notification failed: %s", e)


def _zip_centroid(zip_code: str) -> Optional[tuple[float, float]]:
    res = get_supabase().table("us_zip_codes").select("lat,lng").eq(
        "zip", zip_code
    ).single().execute()
    row = res.data
    if not row or row.get("lat") is None or row.get("lng") is None:
        return None
    return float(row["lat"]), float(row["lng"])


def _filter_and_upsert(
    workspace_id: str,
    job_id: str,
    places: list[dict[str, Any]],
    *,
    exclude_chains: bool,
    min_rating: Optional[float],
    min_reviews: Optional[int],
) -> int:
    rows: list[dict[str, Any]] = []
    for p in places:
        norm = normalize_place(p)
        if not norm.get("place_id") or not norm.get("name"):
            continue
        if exclude_chains and _is_chain(norm["name"]):
            continue
        if min_rating is not None and (norm.get("rating") or 0) < min_rating:
            continue
        if min_reviews is not None and (norm.get("review_count") or 0) < min_reviews:
            continue
        rows.append({"workspace_id": workspace_id, "scrape_job_id": job_id, **norm})

    if not rows:
        return 0

    get_supabase().table("companies").upsert(
        rows, on_conflict="workspace_id,place_id"
    ).execute()
    return len(rows)


async def _run_async(
    workspace_id: str, job_id: str, zip_code: str, keyword: str
) -> tuple[int, int, int, int]:
    """Returns (completed, failed, records_found, api_calls) delta for counters."""
    sb = get_supabase()

    # Verify the job hasn't been cancelled before we do any paid work.
    job = sb.table("scrape_jobs").select(
        "status,radius_miles,two_pass_mode,min_rating,min_reviews,exclude_chains"
    ).eq("id", job_id).single().execute().data
    if not job or job.get("status") == "cancelled":
        return (0, 1, 0, 0)

    centroid = _zip_centroid(zip_code)
    if not centroid:
        log.warning("task: unknown zip %s (job %s)", zip_code, job_id)
        return (0, 1, 0, 0)

    radius_m = _miles_to_meters(job.get("radius_miles") or 10)
    two_pass = bool(job.get("two_pass_mode", True))
    min_rating = job.get("min_rating")
    min_reviews = job.get("min_reviews")
    exclude_chains = bool(job.get("exclude_chains"))

    # Retry up to 2 distinct keys on 429 before giving up.
    api_calls = 0
    last_err: Optional[str] = None
    for attempt in range(2):
        key = api_key_pool.checkout(workspace_id)
        if not key:
            last_err = "No API key with remaining quota"
            break

        client = GooglePlacesClient(key.key_value)
        try:
            places, calls = await client.text_search(
                query=keyword,
                lat=centroid[0],
                lng=centroid[1],
                radius_meters=radius_m,
                min_rating=min_rating,
            )
            api_calls += calls

            if not two_pass:
                enriched: list[dict[str, Any]] = []
                for p in places:
                    pid = p.get("id")
                    if not pid:
                        continue
                    try:
                        detail, dcalls = await client.place_details(pid)
                        api_calls += dcalls
                        enriched.append(detail)
                    except GooglePlacesError:
                        enriched.append(p)
                places = enriched

            inserted = _filter_and_upsert(
                workspace_id, job_id, places,
                exclude_chains=exclude_chains,
                min_rating=min_rating,
                min_reviews=min_reviews,
            )
            return (1, 0, inserted, api_calls)

        except GooglePlacesError as e:
            last_err = str(e)
            if last_err == "rate_limited":
                api_key_pool.flag(workspace_id, key.id, status="rate-limited", error="429")
                continue  # try a different key
            api_key_pool.flag(workspace_id, key.id, status="active", error=last_err[:200])
            break
        except Exception as e:  # pragma: no cover
            last_err = str(e)
            log.exception("scrape task %s/%s crashed", zip_code, keyword)
            break

    log.warning("scrape task failed (%s, %s): %s", zip_code, keyword, last_err)
    return (0, 1, 0, api_calls)


def run_scrape_task(workspace_id: str, job_id: str, zip_code: str, keyword: str) -> None:
    """RQ entrypoint. Sync wrapper around the async worker body."""
    completed, failed, records_found, api_calls = asyncio.run(
        _run_async(workspace_id, job_id, zip_code, keyword)
    )
    _bump_counters(
        job_id,
        completed=completed,
        failed=failed,
        records_found=records_found,
        api_calls=api_calls,
    )
