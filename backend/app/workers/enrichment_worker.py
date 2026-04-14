"""Enrichment worker — runs Apollo or CompanyEnrich for a single company.

Enqueued one-per-company by /api/enrichment/jobs/{id}/run. Keeps the
`enrichment_jobs.completed_records / credits_used` counters atomic via an RPC.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.db.supabase_client import get_supabase
from app.services.apollo import ApolloError, enrich_company as apollo_enrich
from app.services.companyenrich import CompanyEnrichError, enrich_company as ce_enrich

log = logging.getLogger(__name__)


def _bump_enrichment_job(job_id: str, *, completed: int, credits: int) -> None:
    get_supabase().rpc(
        "bump_enrichment_job_counters",
        {
            "p_job_id": job_id,
            "p_completed": completed,
            "p_credits": credits,
        },
    ).execute()


def _load_settings(workspace_id: str) -> dict:
    res = get_supabase().table("workspace_settings").select("*").eq(
        "workspace_id", workspace_id,
    ).single().execute()
    return res.data or {}


def _upsert_contacts(
    company_id: str, workspace_id: str, contacts: list[dict],
) -> int:
    if not contacts:
        return 0
    sb = get_supabase()
    inserted = 0
    for c in contacts:
        email = (c.get("email") or "").lower().strip() or None
        # Skip exact dupes: same company_id + same email (case-insensitive).
        if email:
            dup = sb.table("contacts").select("id").eq(
                "company_id", company_id,
            ).ilike("email", email).limit(1).execute()
            if dup.data:
                continue
        sb.table("contacts").insert({
            "workspace_id": workspace_id,
            "company_id": company_id,
            **c,
            "email": email,
        }).execute()
        inserted += 1
    return inserted


async def _run_async(job_id: str, workspace_id: str, company_id: str, provider: str) -> int:
    sb = get_supabase()
    job_res = sb.table("enrichment_jobs").select("status").eq("id", job_id).single().execute()
    if job_res.data and job_res.data.get("status") == "cancelled":
        return 0

    company = sb.table("companies").select("*").eq("workspace_id", workspace_id).eq(
        "id", company_id,
    ).single().execute().data
    if not company:
        log.warning("enrichment: company %s missing", company_id)
        return 0

    settings = _load_settings(workspace_id)
    title_filters = settings.get("default_title_filters") or [
        "owner", "founder", "ceo", "president", "general manager",
    ]
    cap = int(settings.get("default_contact_cap") or 3)

    try:
        if provider == "apollo":
            firmographics, contacts = await apollo_enrich(
                api_key=settings.get("apollo_api_key") or "",
                company=company,
                title_filters=title_filters,
                contact_cap=cap,
            )
            enriched_field = "apollo_enriched_at"
        elif provider == "companyenrich":
            firmographics, contacts = await ce_enrich(
                api_key=settings.get("companyenrich_api_key") or "",
                company=company,
                contact_cap=cap,
            )
            enriched_field = "companyenrich_enriched_at"
        else:
            raise ValueError(f"Unknown provider: {provider}")
    except (ApolloError, CompanyEnrichError) as e:
        log.warning("enrichment %s failed for company %s: %s", provider, company_id, e)
        return 0

    # Merge firmographics onto company (non-null values only, never clobber).
    update = {k: v for k, v in firmographics.items() if v is not None}
    update[enriched_field] = datetime.now(timezone.utc).isoformat()
    sb.table("companies").update(update).eq("id", company_id).execute()

    inserted = _upsert_contacts(company_id, workspace_id, contacts)
    log.info("enrichment %s: company %s +%d contacts", provider, company_id, inserted)
    return 1  # credits used (approx — 1 credit per enrichment call)


def run_enrichment_task(job_id: str, workspace_id: str, company_id: str, provider: str) -> None:
    credits = asyncio.run(_run_async(job_id, workspace_id, company_id, provider))
    _bump_enrichment_job(job_id, completed=1, credits=credits)
