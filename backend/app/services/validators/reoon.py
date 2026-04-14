"""Reoon validator — self-hosted or SaaS. Uses /v2/verify/?email=&key=…"""
import asyncio
from typing import Any
import httpx

from app.services.validators.base import EmailValidator, ValidationResult, normalize_status

URL = "https://emailverifier.reoon.com/api/v1/verify"


class ReoonValidator(EmailValidator):
    provider_name = "reoon"

    async def validate_bulk(self, emails: list[str]) -> list[ValidationResult]:
        sem = asyncio.Semaphore(10)
        async with httpx.AsyncClient(timeout=30) as client:
            async def one(email: str) -> ValidationResult:
                async with sem:
                    try:
                        resp = await client.get(
                            URL, params={"email": email, "key": self.api_key, "mode": "quick"},
                        )
                        data: dict[str, Any] = resp.json() if resp.is_success else {}
                    except Exception as e:
                        return ValidationResult(email=email, status="unknown", score=0, reason=str(e))

                status = normalize_status(data.get("status") or data.get("result") or "")
                score = int(data.get("score") or
                            {"valid": 95, "catch-all": 55, "risky": 40, "unknown": 30, "invalid": 5}.get(status, 0))
                return ValidationResult(email=email, status=status, score=score, reason=data.get("reason"))

            return await asyncio.gather(*[one(e) for e in emails])
