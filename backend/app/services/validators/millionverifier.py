"""MillionVerifier validator — /api/v3/?api={key}&email=… per email."""
import asyncio
from typing import Any
import httpx

from app.services.validators.base import EmailValidator, ValidationResult, normalize_status

URL = "https://api.millionverifier.com/api/v3/"


class MillionVerifierValidator(EmailValidator):
    provider_name = "millionverifier"

    async def validate_bulk(self, emails: list[str]) -> list[ValidationResult]:
        sem = asyncio.Semaphore(10)
        async with httpx.AsyncClient(timeout=30) as client:
            async def one(email: str) -> ValidationResult:
                async with sem:
                    try:
                        resp = await client.get(
                            URL, params={"api": self.api_key, "email": email, "timeout": 20},
                        )
                        data: dict[str, Any] = resp.json() if resp.is_success else {}
                    except Exception as e:
                        return ValidationResult(email=email, status="unknown", score=0, reason=str(e))

                raw = (data.get("resultcode") or data.get("result") or "").lower()
                status = normalize_status(raw)
                score = {"valid": 95, "catch-all": 55, "risky": 40, "unknown": 30, "invalid": 5}.get(status, 0)
                return ValidationResult(email=email, status=status, score=score, reason=raw)

            return await asyncio.gather(*[one(e) for e in emails])
