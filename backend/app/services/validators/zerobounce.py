"""ZeroBounce validator — /v2/validate per email, parallelized."""
import asyncio
from typing import Any
import httpx

from app.services.validators.base import EmailValidator, ValidationResult, normalize_status

SINGLE_URL = "https://api.zerobounce.net/v2/validate"


class ZeroBounceValidator(EmailValidator):
    provider_name = "zerobounce"

    async def validate_bulk(self, emails: list[str]) -> list[ValidationResult]:
        sem = asyncio.Semaphore(10)
        async with httpx.AsyncClient(timeout=30) as client:
            async def one(email: str) -> ValidationResult:
                async with sem:
                    try:
                        resp = await client.get(
                            SINGLE_URL, params={"api_key": self.api_key, "email": email},
                        )
                        data: dict[str, Any] = resp.json() if resp.is_success else {}
                    except Exception as e:
                        return ValidationResult(email=email, status="unknown", score=0, reason=str(e))

                status = normalize_status(data.get("status", ""))
                score = {"valid": 95, "catch-all": 60, "risky": 40, "unknown": 30, "invalid": 5}.get(status, 0)
                return ValidationResult(email=email, status=status, score=score, reason=data.get("sub_status"))

            return await asyncio.gather(*[one(e) for e in emails])
