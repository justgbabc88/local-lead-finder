from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    email: str
    status: str  # valid | risky | invalid | unknown | catch-all
    score: int   # 0-100
    reason: Optional[str] = None


def normalize_status(raw: str) -> str:
    """Map each provider's native status vocabulary onto our standard set."""
    s = (raw or "").lower().strip()
    if s in {"valid", "deliverable", "ok", "safe_to_send"}:
        return "valid"
    if s in {"invalid", "undeliverable", "bounced", "bad"}:
        return "invalid"
    if s in {"risky", "accept_all", "unknown_type", "disposable", "role", "role_address"}:
        return "risky"
    if s in {"catch_all", "catch-all", "accept-all", "accept_all"}:
        return "catch-all"
    return "unknown"


class EmailValidator(ABC):
    provider_name: str = "base"

    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    async def validate_bulk(self, emails: list[str]) -> list[ValidationResult]:
        """Validate a list of emails. Implementation may batch under the hood."""
