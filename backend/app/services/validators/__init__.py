"""Pluggable email validators — factory returns the provider selected in
workspace_settings.validation_provider."""
from typing import Optional
from app.services.validators.base import EmailValidator, ValidationResult
from app.services.validators.neverbounce import NeverBounceValidator
from app.services.validators.zerobounce import ZeroBounceValidator
from app.services.validators.millionverifier import MillionVerifierValidator
from app.services.validators.reoon import ReoonValidator


def get_validator(provider: str, api_key: Optional[str]) -> EmailValidator:
    if not api_key:
        raise ValueError(f"No API key configured for validation provider '{provider}'")
    if provider == "neverbounce":
        return NeverBounceValidator(api_key)
    if provider == "zerobounce":
        return ZeroBounceValidator(api_key)
    if provider == "millionverifier":
        return MillionVerifierValidator(api_key)
    if provider == "reoon":
        return ReoonValidator(api_key)
    raise ValueError(f"Unknown validation provider: {provider}")


__all__ = ["EmailValidator", "ValidationResult", "get_validator"]
