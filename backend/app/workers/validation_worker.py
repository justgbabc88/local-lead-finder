"""Validation worker — validates a batch of contacts at once.

Unlike scrape/enrichment, validation batches well on the provider side (the
validator classes fan out internally with asyncio.Semaphore), so we dispatch
one worker job per batch of ~50 contacts.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.db.supabase_client import get_supabase
from app.services.validators import get_validator

log = logging.getLogger(__name__)


def _load_settings(workspace_id: str) -> dict:
    res = get_supabase().table("workspace_settings").select("*").eq(
        "workspace_id", workspace_id,
    ).single().execute()
    return res.data or {}


def _bump(job_id: str, *, completed: int, valid: int, invalid: int, risky: int) -> None:
    get_supabase().rpc(
        "bump_validation_job_counters",
        {
            "p_job_id": job_id,
            "p_completed": completed,
            "p_valid": valid,
            "p_invalid": invalid,
            "p_risky": risky,
        },
    ).execute()


async def _run_async(job_id: str, workspace_id: str, contact_ids: list[str]) -> None:
    sb = get_supabase()
    settings = _load_settings(workspace_id)
    provider = settings.get("validation_provider") or "neverbounce"
    api_key = settings.get(f"{provider}_api_key")

    contacts_res = sb.table("contacts").select("id, email").in_("id", contact_ids).execute()
    contacts = [c for c in (contacts_res.data or []) if c.get("email")]
    if not contacts:
        _bump(job_id, completed=len(contact_ids), valid=0, invalid=0, risky=0)
        return

    try:
        validator = get_validator(provider, api_key)
    except ValueError as e:
        log.error("validation: %s", e)
        _bump(job_id, completed=len(contact_ids), valid=0, invalid=0, risky=0)
        return

    emails = [c["email"] for c in contacts]
    results = await validator.validate_bulk(emails)
    result_by_email = {r.email.lower(): r for r in results}

    valid = invalid = risky = 0
    now = datetime.now(timezone.utc).isoformat()
    for c in contacts:
        email = (c.get("email") or "").lower()
        r = result_by_email.get(email)
        if not r:
            continue

        if r.status == "valid":
            valid += 1
        elif r.status == "invalid":
            invalid += 1
        elif r.status in ("risky", "catch-all"):
            risky += 1

        sb.table("contacts").update({
            "email_status": r.status,
            "email_confidence": r.score,
            "validated_at": now,
        }).eq("id", c["id"]).execute()

        # Auto-suppress: add any confirmed-invalid emails to the workspace suppression list
        # so Email Bison pushes and CSV exports skip them automatically.
        if r.status == "invalid":
            try:
                sb.table("suppression_list").insert({
                    "workspace_id": workspace_id,
                    "type": "email",
                    "value": email,
                    "reason": f"validation:{provider}",
                }).execute()
            except Exception:
                pass  # unique (workspace_id, type, value) conflicts are fine

    _bump(job_id, completed=len(contact_ids), valid=valid, invalid=invalid, risky=risky)


def run_validation_task(job_id: str, workspace_id: str, contact_ids: list[str]) -> None:
    asyncio.run(_run_async(job_id, workspace_id, contact_ids))
