"""Scrape orchestration (Phase 1: synchronous).

Iterates zip × keyword combinations, calls Google Places, upserts companies, and
updates the scrape_jobs row as it progresses. Phase 2 will replace this sync
runner with a Redis queue + parallel Railway workers.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from app.config import get_settings
from app.db.supabase_client import get_supabase
from app.services.google_places import GooglePlacesClient, GooglePlacesError, normalize_place

log = logging.getLogger(__name__)

# Known national chain substrings — used when exclude_chains is on.
# Phase 2+ should move this to a workspace-editable list.
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


def _update_job(job_id: str, **fields: Any) -> None:
    get_supabase().table("scrape_jobs").update(fields).eq("id", job_id).execute()


def _zip_centroids(zip_codes: Iterable[str]) -> dict[str, tuple[float, float]]:
    sb = get_supabase()
    res = sb.table("us_zip_codes").select("zip,lat,lng").in_("zip", list(zip_codes)).execute()
    return {
        row["zip"]: (float(row["lat"]), float(row["lng"]))
        for row in (res.data or [])
        if row.get("lat") is not None and row.get("lng") is not None
    }


def _upsert_companies(
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
        rows.append({
            "workspace_id": workspace_id,
            "scrape_job_id": job_id,
            **norm,
        })

    if not rows:
        return 0

    # Upsert on (workspace_id, place_id) — updates existing companies with fresh data.
    get_supabase().table("companies").upsert(
        rows,
        on_conflict="workspace_id,place_id",
    ).execute()
    return len(rows)


async def run_scrape_job(job_id: str) -> None:
    """Run an entire scrape job synchronously. Invoked from a FastAPI BackgroundTask."""
    sb = get_supabase()
    settings = get_settings()

    job_res = sb.table("scrape_jobs").select("*").eq("id", job_id).single().execute()
    job = job_res.data
    if not job:
        log.error("scrape job %s not found", job_id)
        return

    workspace_id: str = job["workspace_id"]
    keywords: list[str] = job["niche_keywords"] or []
    zips: list[str] = job["zip_codes"] or []
    radius_m = _miles_to_meters(job.get("radius_miles") or 10)
    two_pass = bool(job.get("two_pass_mode", True))
    min_rating = job.get("min_rating")
    min_reviews = job.get("min_reviews")
    exclude_chains = bool(job.get("exclude_chains"))

    centroids = _zip_centroids(zips)
    tasks = [(z, k) for z in zips for k in keywords if z in centroids]
    total_tasks = len(tasks)

    _update_job(
        job_id,
        status="running",
        total_tasks=total_tasks,
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    # Resolve API key: Phase 1 = env fallback. Phase 2+ = pool from api_keys_google.
    api_key = settings.google_places_api_key
    if not api_key:
        keys = sb.table("api_keys_google").select("key_value").eq(
            "workspace_id", workspace_id
        ).eq("status", "active").limit(1).execute()
        if keys.data:
            api_key = keys.data[0]["key_value"]

    if not api_key:
        _update_job(
            job_id,
            status="error",
            error_message="No Google Places API key configured (env or api_keys_google pool).",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        return

    client = GooglePlacesClient(api_key)

    completed = 0
    failed = 0
    records_found = 0
    api_calls = 0

    try:
        for zip_code, keyword in tasks:
            lat, lng = centroids[zip_code]
            try:
                places, calls = await client.text_search(
                    query=keyword,
                    lat=lat,
                    lng=lng,
                    radius_meters=radius_m,
                    min_rating=min_rating,
                )
                api_calls += calls

                # Phase 1 two-pass: in two-pass mode we skip Place Details here
                # and save text-search fields only. Single-pass fetches details inline.
                if not two_pass:
                    enriched = []
                    for p in places:
                        pid = p.get("id")
                        if not pid:
                            continue
                        try:
                            detail, dcalls = await client.place_details(pid)
                            api_calls += dcalls
                            enriched.append(detail)
                        except GooglePlacesError as e:
                            log.warning("details failed for %s: %s", pid, e)
                            enriched.append(p)
                    places = enriched

                inserted = _upsert_companies(
                    workspace_id, job_id, places,
                    exclude_chains=exclude_chains,
                    min_rating=min_rating,
                    min_reviews=min_reviews,
                )
                records_found += inserted
                completed += 1
            except GooglePlacesError as e:
                failed += 1
                log.warning("task failed (%s, %s): %s", zip_code, keyword, e)
            except Exception as e:  # pragma: no cover
                failed += 1
                log.exception("unexpected task error (%s, %s): %s", zip_code, keyword, e)

            _update_job(
                job_id,
                completed_tasks=completed,
                failed_tasks=failed,
                records_found=records_found,
                api_calls_made=api_calls,
            )

        # $32 per 1000 text-search calls is Google's v1 enterprise price — rough estimate only.
        est_cost = round(api_calls * 0.032, 4)
        _update_job(
            job_id,
            status="complete",
            completed_at=datetime.now(timezone.utc).isoformat(),
            estimated_cost_usd=est_cost,
        )
    except Exception as e:  # pragma: no cover
        log.exception("scrape job %s crashed", job_id)
        _update_job(
            job_id,
            status="error",
            error_message=str(e),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


async def fetch_details_for_companies(workspace_id: str, company_ids: list[str]) -> int:
    """Second-pass Place Details fetch for specific companies. Returns # updated."""
    sb = get_supabase()
    settings = get_settings()
    api_key = settings.google_places_api_key
    if not api_key:
        keys = sb.table("api_keys_google").select("key_value").eq(
            "workspace_id", workspace_id
        ).eq("status", "active").limit(1).execute()
        if keys.data:
            api_key = keys.data[0]["key_value"]
    if not api_key:
        raise GooglePlacesError("No Google Places API key configured")

    res = sb.table("companies").select("id,place_id").eq(
        "workspace_id", workspace_id
    ).in_("id", company_ids).execute()

    client = GooglePlacesClient(api_key)
    updated = 0
    for row in res.data or []:
        pid = row.get("place_id")
        if not pid:
            continue
        try:
            detail, _ = await client.place_details(pid)
            norm = normalize_place(detail)
            # Don't clobber the place_id/workspace_id fields on update
            norm.pop("place_id", None)
            sb.table("companies").update(norm).eq("id", row["id"]).execute()
            updated += 1
        except GooglePlacesError as e:
            log.warning("details refresh failed for %s: %s", pid, e)
    return updated
