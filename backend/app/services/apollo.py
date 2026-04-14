"""Apollo.io enrichment.

Resolves a company domain → organization record, then searches for decision-maker
contacts with the workspace's default title filters. Returns a list of contact
dicts ready to upsert into `contacts`.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

ORG_ENRICH_URL = "https://api.apollo.io/v1/organizations/enrich"
PEOPLE_SEARCH_URL = "https://api.apollo.io/v1/mixed_people/search"


class ApolloError(Exception):
    pass


def _domain_from_website(website: Optional[str]) -> Optional[str]:
    if not website:
        return None
    try:
        host = urlparse(website if "//" in website else f"https://{website}").hostname or ""
        return host.lower().removeprefix("www.") or None
    except Exception:
        return None


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "X-Api-Key": api_key,
    }


async def enrich_company(
    *,
    api_key: str,
    company: dict[str, Any],
    title_filters: list[str],
    contact_cap: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return (org_data, contacts). Raises ApolloError on fatal failures."""
    if not api_key:
        raise ApolloError("Apollo API key not configured")

    domain = _domain_from_website(company.get("website"))
    if not domain:
        raise ApolloError("No domain on company — cannot enrich")

    async with httpx.AsyncClient(timeout=30) as client:
        org_resp = await client.get(
            ORG_ENRICH_URL, params={"domain": domain}, headers=_headers(api_key)
        )
        if org_resp.status_code == 401:
            raise ApolloError("Apollo auth failed — check API key")
        if org_resp.status_code >= 400:
            raise ApolloError(f"Apollo org enrich {org_resp.status_code}: {org_resp.text[:200]}")
        org = (org_resp.json() or {}).get("organization") or {}

        people_body: dict[str, Any] = {
            "organization_domains": [domain],
            "per_page": max(1, min(contact_cap, 25)),
            "page": 1,
        }
        if title_filters:
            people_body["person_titles"] = title_filters

        people_resp = await client.post(
            PEOPLE_SEARCH_URL, json=people_body, headers=_headers(api_key)
        )
        if people_resp.status_code >= 400:
            raise ApolloError(f"Apollo people search {people_resp.status_code}: {people_resp.text[:200]}")
        people = (people_resp.json() or {}).get("people") or []

    contacts: list[dict[str, Any]] = []
    for p in people[:contact_cap]:
        email = p.get("email")
        # Apollo returns placeholder strings like "email_not_unlocked@domain.com".
        if email and "email_not_unlocked" in email.lower():
            email = None

        contacts.append({
            "first_name": p.get("first_name"),
            "last_name": p.get("last_name"),
            "full_name": p.get("name"),
            "title": p.get("title"),
            "seniority": p.get("seniority"),
            "email": email,
            "email_status": "unvalidated" if email else None,
            "email_source": "apollo" if email else None,
            "email_confidence": 80 if email else None,
            "phone": (p.get("organization", {}) or {}).get("phone") or p.get("phone"),
            "linkedin_url": p.get("linkedin_url"),
            "apollo_id": p.get("id"),
        })

    firmographics = {
        "employee_count": org.get("estimated_num_employees"),
        "revenue_estimate": org.get("estimated_annual_revenue") or org.get("annual_revenue_printed"),
        "year_founded": org.get("founded_year"),
        "tech_stack": [t.get("name") for t in (org.get("current_technologies") or []) if t.get("name")] or None,
        "linkedin_url": org.get("linkedin_url"),
        "facebook_url": org.get("facebook_url"),
        "instagram_url": org.get("twitter_url"),  # Apollo uses 'twitter_url' etc.
    }

    return firmographics, contacts
