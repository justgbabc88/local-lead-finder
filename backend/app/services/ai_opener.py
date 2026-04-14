"""AI personalization — 1-2 sentence cold-email openers via Claude."""
from __future__ import annotations

from typing import Optional
import httpx

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"


class AIOpenerError(Exception):
    pass


def _build_prompt(*, contact_name: str, company_name: str, category: Optional[str],
                  rating: Optional[float], review_count: Optional[int],
                  website_snippet: Optional[str]) -> str:
    parts = [
        f"Write a single 1-2 sentence personalized cold email opener for "
        f"{contact_name} at {company_name}",
    ]
    if category:
        parts.append(f", a {category} business")
    if review_count and rating:
        parts.append(f". They have {review_count} reviews averaging {rating} stars")
    if website_snippet:
        parts.append(f'. Their website says: "{website_snippet[:400]}"')
    parts.append(
        ". Make it specific, conversational, and not salesy. No subject line. "
        "Output only the opener, no preamble."
    )
    return "".join(parts)


async def generate_opener(
    *,
    api_key: str,
    contact_name: str,
    company_name: str,
    category: Optional[str] = None,
    rating: Optional[float] = None,
    review_count: Optional[int] = None,
    website_snippet: Optional[str] = None,
) -> str:
    if not api_key:
        raise AIOpenerError("Anthropic API key not configured")

    prompt = _build_prompt(
        contact_name=contact_name, company_name=company_name,
        category=category, rating=rating, review_count=review_count,
        website_snippet=website_snippet,
    )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        if resp.status_code >= 400:
            raise AIOpenerError(f"Anthropic {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        content = data.get("content") or []
        for block in content:
            if block.get("type") == "text":
                return (block.get("text") or "").strip()
        raise AIOpenerError("Empty response from Anthropic")
