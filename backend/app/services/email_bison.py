"""Email Bison integration.

Email Bison is self-hosted so the base URL is workspace-specific. The exact
endpoint paths vary by Bison version — this module is written against the
common v1 REST layout. If a workspace's instance differs, adjust the paths
constants in one place.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

log = logging.getLogger(__name__)


class EmailBisonError(Exception):
    pass


class EmailBisonClient:
    def __init__(self, base_url: str, api_key: str):
        if not base_url:
            raise EmailBisonError("Email Bison base URL not configured")
        if not api_key:
            raise EmailBisonError("Email Bison API key not configured")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _get(self, path: str, params: Optional[dict] = None) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{self.base_url}{path}", headers=self._headers(), params=params)
            if r.status_code >= 400:
                raise EmailBisonError(f"GET {path} {r.status_code}: {r.text[:200]}")
            return r.json()

    async def _post(self, path: str, body: Any) -> Any:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{self.base_url}{path}", headers=self._headers(), json=body)
            if r.status_code >= 400:
                raise EmailBisonError(f"POST {path} {r.status_code}: {r.text[:200]}")
            return r.json() if r.content else {}

    # ----- Campaigns -----
    async def list_campaigns(self) -> list[dict]:
        data = await self._get("/api/campaigns")
        # Typical envelope: { campaigns: [...] } or raw list.
        return data.get("campaigns") if isinstance(data, dict) and "campaigns" in data else data or []

    async def get_campaign_analytics(self, campaign_id: str) -> dict:
        return await self._get(f"/api/campaigns/{campaign_id}/analytics")

    # ----- Contacts push -----
    async def push_contacts(self, campaign_id: str, contacts: list[dict]) -> dict:
        return await self._post(f"/api/campaigns/{campaign_id}/contacts", {"contacts": contacts})

    # ----- Mailboxes -----
    async def list_mailboxes(self) -> list[dict]:
        data = await self._get("/api/mailboxes")
        return data.get("mailboxes") if isinstance(data, dict) and "mailboxes" in data else data or []


def map_contact(contact: dict, company: dict, mapping: dict[str, str]) -> dict:
    """Apply the workspace field-mapping to a (contact, company) pair.

    `mapping` is a dict of {email_bison_field: source_field_name}. Source fields
    can reference `contact.*` or `company.*` directly (e.g. 'contact.email',
    'company.city').
    """
    mapped: dict[str, Any] = {}
    for dest, src in mapping.items():
        if not isinstance(src, str):
            continue
        if src.startswith("contact."):
            mapped[dest] = contact.get(src.removeprefix("contact."))
        elif src.startswith("company."):
            mapped[dest] = company.get(src.removeprefix("company."))
        else:
            # literal — carry the string through so users can inject constants
            mapped[dest] = src
    return mapped
