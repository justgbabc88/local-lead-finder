"""Notification helpers — creates in-app notifications and optionally forwards
to Slack (if a webhook is configured)."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.db.supabase_client import get_supabase

log = logging.getLogger(__name__)


def notify(
    *,
    workspace_id: str,
    type: str,
    title: str,
    body: Optional[str] = None,
    link: Optional[str] = None,
) -> None:
    sb = get_supabase()
    sb.table("notifications").insert({
        "workspace_id": workspace_id,
        "type": type,
        "title": title,
        "body": body,
        "link": link,
    }).execute()

    # Best-effort Slack mirror.
    settings = sb.table("workspace_settings").select("slack_webhook_url").eq(
        "workspace_id", workspace_id,
    ).single().execute().data or {}
    url = settings.get("slack_webhook_url")
    if not url:
        return
    try:
        httpx.post(url, json={"text": f"*{title}*\n{body or ''}\n{link or ''}".strip()}, timeout=10)
    except Exception as e:  # pragma: no cover
        log.warning("slack post failed: %s", e)
