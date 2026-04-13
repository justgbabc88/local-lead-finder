"""Supabase client factory.

We use the service-role key server-side — RLS does NOT apply to the service key,
so every query MUST manually filter by workspace_id. The auth layer validates
the user's workspace membership before any handler runs.
"""
from functools import lru_cache
from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)
