"""Domain Health Monitor — SPF / DKIM / DMARC / MX / blacklist / age / DNS."""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import dns.exception
import dns.resolver
import httpx

log = logging.getLogger(__name__)

DOMAIN_RBLS = [
    "dbl.spamhaus.org",
    "multi.surbl.org",
    "black.uribl.com",
    "fresh.spameatingmonkey.net",
    "dnsbl.spfbl.net",
]

COMMON_DKIM_SELECTORS = ["google", "mail", "s1", "s2", "k1", "default", "smtp", "dkim"]


class DomainHealthChecker:
    def __init__(self, mxtoolbox_api_key: Optional[str] = None):
        self.mxtoolbox_key = mxtoolbox_api_key

    async def run_full_check(self, domain: str, dkim_selector: Optional[str] = None) -> dict[str, Any]:
        results: dict[str, Any] = {}
        results["spf"] = self.check_spf(domain)
        results["dkim"] = self.check_dkim(domain, dkim_selector)
        results["dmarc"] = self.check_dmarc(domain)
        results["mx"] = self.check_mx(domain)
        results["blacklist"] = await self.check_blacklist(domain)
        results["domain_age"] = self.check_domain_age(domain)
        results["dns"] = self.check_dns(domain)
        results["score"] = self.calculate_score(results)
        results["status"] = self.score_to_status(results["score"])
        return results

    # ---------- SPF ----------
    def check_spf(self, domain: str) -> dict[str, Any]:
        try:
            answers = dns.resolver.resolve(domain, "TXT")
            spf = [str(r).strip('"') for r in answers if "v=spf1" in str(r)]
            if not spf:
                return {"exists": False, "status": "fail", "issue": "No SPF record found"}
            if len(spf) > 1:
                return {"exists": True, "record": spf[0], "status": "fail",
                        "issue": "Multiple SPF records found — only one is allowed"}

            record = spf[0]
            lookup_count = sum(1 for m in ["include:", "a:", "mx", "ptr", "exists:"] if m in record)
            if lookup_count > 10:
                return {"exists": True, "record": record, "status": "fail",
                        "issue": f"SPF exceeds 10 DNS lookup limit ({lookup_count} lookups)",
                        "lookup_count": lookup_count}
            if "?all" in record:
                return {"exists": True, "record": record, "status": "warning",
                        "issue": "SPF uses ?all (neutral) — use -all for strict enforcement",
                        "lookup_count": lookup_count}
            if "~all" in record:
                return {"exists": True, "record": record, "status": "warning",
                        "issue": "SPF uses ~all (soft fail) — consider -all for better protection",
                        "lookup_count": lookup_count}
            return {"exists": True, "record": record, "status": "pass",
                    "lookup_count": lookup_count}
        except dns.exception.DNSException as e:
            return {"exists": False, "status": "fail", "issue": str(e)}

    # ---------- DMARC ----------
    def check_dmarc(self, domain: str) -> dict[str, Any]:
        try:
            answers = dns.resolver.resolve(f"_dmarc.{domain}", "TXT")
            recs = [str(r).strip('"') for r in answers if "v=DMARC1" in str(r)]
            if not recs:
                return {"exists": False, "status": "fail",
                        "issue": "No DMARC record — required by Google/Yahoo since 2024"}
            r = recs[0]
            if "p=reject" in r:
                return {"exists": True, "record": r, "policy": "reject", "status": "pass"}
            if "p=quarantine" in r:
                return {"exists": True, "record": r, "policy": "quarantine", "status": "pass"}
            if "p=none" in r:
                return {"exists": True, "record": r, "policy": "none", "status": "warning",
                        "issue": "DMARC policy is p=none — upgrade to quarantine or reject"}
            return {"exists": True, "record": r, "status": "warning",
                    "issue": "DMARC policy could not be parsed"}
        except dns.exception.DNSException as e:
            return {"exists": False, "status": "fail", "issue": str(e)}

    # ---------- DKIM ----------
    def check_dkim(self, domain: str, selector: Optional[str] = None) -> dict[str, Any]:
        selectors = [selector] if selector else COMMON_DKIM_SELECTORS
        for sel in selectors:
            if not sel:
                continue
            try:
                answers = dns.resolver.resolve(f"{sel}._domainkey.{domain}", "TXT")
                recs = [str(r).strip('"') for r in answers if "v=DKIM1" in str(r)]
                if not recs:
                    continue
                record = recs[0]
                key_bits: Optional[int] = None
                if "p=" in record:
                    key_b64 = record.split("p=")[-1].split(";")[0].strip()
                    try:
                        key_bits = len(base64.b64decode(key_b64 + "==")) * 8
                    except Exception:
                        pass
                status, issue = "pass", None
                if key_bits and key_bits < 1024:
                    status, issue = "warning", f"DKIM key is only {key_bits} bits — 2048-bit recommended"
                return {"exists": True, "selector": sel, "record": record,
                        "status": status, "key_bits": key_bits, "issue": issue}
            except dns.exception.DNSException:
                continue
        return {"exists": False, "status": "warning",
                "issue": "No DKIM record found at common selectors — set your platform's selector in settings"}

    # ---------- MX ----------
    def check_mx(self, domain: str) -> dict[str, Any]:
        try:
            answers = dns.resolver.resolve(domain, "MX")
            records = sorted(
                [{"priority": int(r.preference), "host": str(r.exchange).rstrip(".")} for r in answers],
                key=lambda x: x["priority"],
            )
            if not records:
                return {"exists": False, "status": "fail", "issue": "No MX records found"}
            return {"exists": True, "records": records, "status": "pass"}
        except dns.exception.DNSException as e:
            return {"exists": False, "status": "fail", "issue": str(e)}

    # ---------- Blacklist ----------
    async def check_blacklist(self, domain: str) -> dict[str, Any]:
        if self.mxtoolbox_key:
            return await self._blacklist_mxtoolbox(domain)
        return self._blacklist_dns(domain)

    async def _blacklist_mxtoolbox(self, domain: str) -> dict[str, Any]:
        url = f"https://mxtoolbox.com/api/v1/lookup/blacklist/{domain}"
        headers = {"Authorization": self.mxtoolbox_key or ""}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code >= 400:
                    return self._blacklist_dns(domain)
                data = resp.json() or {}
                failed = data.get("Failed") or []
                passed = data.get("Passed") or []
                return {
                    "status": "listed" if failed else "clean",
                    "lists_checked": len(passed) + len(failed),
                    "lists_listed": len(failed),
                    "listed_on": [f.get("Name") for f in failed if f.get("Name")],
                }
        except Exception:
            return self._blacklist_dns(domain)

    def _blacklist_dns(self, domain: str) -> dict[str, Any]:
        listed: list[str] = []
        for rbl in DOMAIN_RBLS:
            try:
                dns.resolver.resolve(f"{domain}.{rbl}", "A")
                listed.append(rbl)
            except dns.resolver.NXDOMAIN:
                pass
            except dns.exception.DNSException:
                pass
        return {
            "status": "listed" if listed else "clean",
            "lists_checked": len(DOMAIN_RBLS),
            "lists_listed": len(listed),
            "listed_on": listed,
            "note": "Basic check (5 RBLs). Add an MxToolbox key in Settings for 100+ list coverage.",
        }

    # ---------- Age ----------
    def check_domain_age(self, domain: str) -> dict[str, Any]:
        try:
            import whois as whois_lib  # type: ignore
            w = whois_lib.whois(domain)
            created = w.creation_date
            if isinstance(created, list):
                created = created[0] if created else None
            if not created:
                return {"status": "unknown", "issue": "Could not determine domain age"}
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - created).days
            if age_days < 30:
                return {"age_days": age_days, "registered_at": created.isoformat(),
                        "status": "fail", "issue": f"Domain is only {age_days} days old — very high spam risk"}
            if age_days < 90:
                return {"age_days": age_days, "registered_at": created.isoformat(),
                        "status": "warning",
                        "issue": f"Domain is {age_days} days old — limited sending reputation"}
            return {"age_days": age_days, "registered_at": created.isoformat(), "status": "pass"}
        except Exception as e:
            log.warning("whois lookup failed for %s: %s", domain, e)
            return {"status": "unknown", "issue": "Could not determine domain age"}

    # ---------- DNS ----------
    def check_dns(self, domain: str) -> dict[str, Any]:
        try:
            dns.resolver.resolve(domain, "A")
            return {"a_record_exists": True, "status": "pass"}
        except dns.exception.DNSException as e:
            return {"a_record_exists": False, "status": "fail", "issue": str(e)}

    # ---------- Score ----------
    def calculate_score(self, results: dict[str, Any]) -> int:
        weights = {"spf": 25, "dkim": 25, "dmarc": 20, "blacklist": 20, "mx": 5, "domain_age": 5}
        score = 0
        for check, max_pts in weights.items():
            r = results.get(check, {})
            status = r.get("status", "fail")
            if check == "blacklist":
                score += max_pts if r.get("status") == "clean" else 0
            elif status == "pass":
                score += max_pts
            elif status == "warning":
                score += int(max_pts * 0.5)
        return min(score, 100)

    def score_to_status(self, score: int) -> str:
        if score >= 80:
            return "healthy"
        if score >= 50:
            return "warning"
        return "critical"
