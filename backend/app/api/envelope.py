"""Standard response envelope: { data, error, meta }."""
from typing import Any, Optional
from pydantic import BaseModel


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: Optional[dict[str, Any]] = None


class Envelope(BaseModel):
    data: Optional[Any] = None
    error: Optional[ErrorPayload] = None
    meta: Optional[dict[str, Any]] = None


def ok(data: Any = None, meta: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": meta}


def err(code: str, message: str, details: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return {"data": None, "error": {"code": code, "message": message, "details": details}, "meta": None}
