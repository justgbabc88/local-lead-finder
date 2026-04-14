"""Domain health daily cron: check every monitored domain, store results,
fire alerts on score drops or blacklist events.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.db.supabase_client import get_supabase
from app.services.domain_health import DomainHealthChecker
from app.services.notify import notify

log = logging.getLogger(__name__)


def _fire_alert(
    *, workspace_id: str, domain: dict, alert_type: str, message: str,
    previous_score: int | None, new_score: int,
) -> None:
    sb = get_supabase()
    sb.table("domain_health_alerts").insert({
        "domain_id": domain["id"],
        "workspace_id": workspace_id,
        "alert_type": alert_type,
        "message": message,
        "previous_score": previous_score,
        "new_score": new_score,
    }).execute()
    notify(
        workspace_id=workspace_id,
        type="domain_alert",
        title=f"Domain alert: {domain['domain']}",
        body=message,
        link="/domain-health",
    )


async def _check_one(domain: dict) -> None:
    sb = get_supabase()
    settings = sb.table("workspace_settings").select("mxtoolbox_api_key").eq(
        "workspace_id", domain["workspace_id"],
    ).single().execute().data or {}

    checker = DomainHealthChecker(mxtoolbox_api_key=settings.get("mxtoolbox_api_key"))
    results: dict[str, Any] = await checker.run_full_check(
        domain["domain"], domain.get("dkim_selector")
    )

    spf = results["spf"]
    dkim = results["dkim"]
    dmarc = results["dmarc"]
    mx = results["mx"]
    bl = results["blacklist"]
    age = results["domain_age"]
    dns_ = results["dns"]

    issues_count = sum(1 for r in [spf, dkim, dmarc, mx, age, dns_]
                       if r.get("status") in ("fail", "warning"))
    if bl.get("status") == "listed":
        issues_count += 1

    sb.table("domain_health_checks").insert({
        "domain_id": domain["id"],
        "workspace_id": domain["workspace_id"],
        "spf_exists": spf.get("exists"),
        "spf_record": spf.get("record"),
        "spf_status": spf.get("status"),
        "spf_issue": spf.get("issue"),
        "spf_lookup_count": spf.get("lookup_count"),
        "dkim_exists": dkim.get("exists"),
        "dkim_selector_used": dkim.get("selector"),
        "dkim_record": dkim.get("record"),
        "dkim_status": dkim.get("status"),
        "dkim_key_bits": dkim.get("key_bits"),
        "dkim_issue": dkim.get("issue"),
        "dmarc_exists": dmarc.get("exists"),
        "dmarc_record": dmarc.get("record"),
        "dmarc_policy": dmarc.get("policy"),
        "dmarc_status": dmarc.get("status"),
        "dmarc_issue": dmarc.get("issue"),
        "mx_exists": mx.get("exists"),
        "mx_records": mx.get("records"),
        "mx_status": mx.get("status"),
        "mx_issue": mx.get("issue"),
        "blacklist_status": bl.get("status"),
        "blacklists_checked": bl.get("lists_checked"),
        "blacklists_listed": bl.get("lists_listed"),
        "blacklisted_on": bl.get("listed_on"),
        "domain_age_days": age.get("age_days"),
        "domain_registered_at": age.get("registered_at"),
        "domain_age_status": age.get("status"),
        "a_record_exists": dns_.get("a_record_exists"),
        "dns_status": dns_.get("status"),
        "overall_score": results["score"],
        "overall_status": results["status"],
        "issues_count": issues_count,
        "raw_results": results,
    }).execute()

    previous_score = domain.get("health_score")
    sb.table("monitored_domains").update({
        "health_score": results["score"],
        "last_checked_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", domain["id"]).execute()

    if domain.get("alert_on_score_drop") and results["score"] < (domain.get("alert_threshold") or 70):
        _fire_alert(
            workspace_id=domain["workspace_id"],
            domain=domain,
            alert_type="score_drop",
            message=f"Health score dropped to {results['score']} "
                    f"(threshold {domain.get('alert_threshold') or 70}).",
            previous_score=previous_score,
            new_score=results["score"],
        )
    if bl.get("status") == "listed":
        _fire_alert(
            workspace_id=domain["workspace_id"],
            domain=domain,
            alert_type="blacklisted",
            message=f"Listed on {bl.get('lists_listed', 0)} blacklist(s): "
                    f"{', '.join((bl.get('listed_on') or [])[:5])}",
            previous_score=previous_score,
            new_score=results["score"],
        )


async def _run_all_async() -> int:
    sb = get_supabase()
    domains = sb.table("monitored_domains").select("*").eq("is_active", True).execute().data or []
    for d in domains:
        try:
            await _check_one(d)
        except Exception as e:  # pragma: no cover
            log.exception("domain health check failed for %s: %s", d.get("domain"), e)
    return len(domains)


def run_all_health_checks() -> int:
    return asyncio.run(_run_all_async())
