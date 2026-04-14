"""NeverBounce validator — uses the single-email /v4/single/check endpoint.

NeverBounce's bulk jobs API is poll-based and adds significant latency; the
single endpoint is fast enough for our per-workspace volumes. We parallelize
10 checks at a time via httpx.
"""
import asyncio
from typing import Any
import httpx

from app.services.validators.base import EmailValidator, ValidationResult, normalize_status

SINGLE_URL = "https://api.neverbounce.com/v4/single/check"


class NeverBounceValidator(EmailValidator):
    provider_name = "neverbounce"

    async def validate_bulk(self, emails: list[str]) -> list[ValidationResult]:
        sem = asyncio.Semaphore(10)
        async with httpx.AsyncClient(timeout=30) as client:
            async def one(email: str) -> ValidationResult:
                async with sem:
                    try:
                        resp = await client.get(
                            SINGLE_URL, params={"key": self.api_key, "email": email}
                        )
                        data: dict[str, Any] = resp.json() if resp.is_success else {}
                    except Exception as e:
                        return ValidationResult(email=email, status="unknown", score=0, reason=str(e))

                result = (data.get("result") or "").lower()
                status = normalize_status(result)
                # NeverBounce doesn't expose a numeric confidence; infer.
                score = {"valid": 95, "catch-all": 55, "risky": 40, "unknown": 30, "invalid": 5}.get(status, 0)
                return ValidationResult(email=email, status=status, score=score, reason=result)

            return await asyncio.gather(*[one(e) for e in emails])
