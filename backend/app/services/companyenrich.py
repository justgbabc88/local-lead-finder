"""CompanyEnrich.com enrichment.

The exact endpoint shape varies by plan — we use the documented GET /enrich
with a `domain` or `name` parameter and normalize the response. Any response
keys not present are simply skipped, so this works across API variants.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

ENRICH_URL = "https://api.companyenrich.com/companies/enrich"


class CompanyEnrichError(Exception):
    pass


def _domain_from_website(website: Optional[str]) -> Optional[str]:
    if not website:
        return None
    try:
        host = urlparse(website if "//" in website else f"https://{website}").hostname or ""
        return host.lower().removeprefix("www.") or None
    except Exception:
        return None


async def enrich_company(
    *, api_key: str, company: dict[str, Any], contact_cap: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not api_key:
        raise CompanyEnrichError("CompanyEnrich API key not configured")

    params: dict[str, Any] = {}
    domain = _domain_from_website(company.get("website"))
    if domain:
        params["domain"] = domain
    elif company.get("name"):
        params["name"] = company["name"]
    else:
        raise CompanyEnrichError("Company has no website or name to enrich")

    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(ENRICH_URL, params=params, headers=headers)
        if resp.status_code == 404:
            return ({}, [])  # no match — treat as empty, not a fatal error
        if resp.status_code == 401:
            raise CompanyEnrichError("CompanyEnrich auth failed — check API key")
        if resp.status_code >= 400:
            raise CompanyEnrichError(f"CompanyEnrich {resp.status_code}: {resp.text[:200]}")
        data = resp.json() or {}

    firmographics = {
        "employee_count": data.get("employees") or data.get("employee_count"),
        "revenue_estimate": data.get("revenue"),
        "year_founded": data.get("founded") or data.get("year_founded"),
        "tech_stack": data.get("technologies") or data.get("tech_stack"),
        "linkedin_url": (data.get("social") or {}).get("linkedin") or data.get("linkedin_url"),
        "facebook_url": (data.get("social") or {}).get("facebook") or data.get("facebook_url"),
        "instagram_url": (data.get("social") or {}).get("instagram") or data.get("instagram_url"),
    }

    contacts: list[dict[str, Any]] = []
    for c in (data.get("contacts") or [])[:contact_cap]:
        email = c.get("email")
        contacts.append({
            "first_name": c.get("first_name"),
            "last_name": c.get("last_name"),
            "full_name": c.get("full_name") or c.get("name"),
            "title": c.get("title"),
            "email": email,
            "email_status": "unvalidated" if email else None,
            "email_source": "companyenrich" if email else None,
            "email_confidence": 70 if email else None,
            "phone": c.get("phone"),
            "linkedin_url": c.get("linkedin"),
        })

    return firmographics, contacts
