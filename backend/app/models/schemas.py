"""Pydantic request/response models."""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ---------- Workspace ----------
class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class WorkspaceOut(BaseModel):
    id: str
    name: str
    owner_id: str
    created_at: datetime
    role: Optional[str] = None


# ---------- Scrape Job ----------
class ScrapeJobCreate(BaseModel):
    niche_keywords: list[str] = Field(..., min_length=1)
    zip_codes: list[str] = Field(..., min_length=1)
    radius_miles: int = Field(10, ge=1, le=50)
    min_rating: Optional[float] = Field(None, ge=0, le=5)
    min_reviews: Optional[int] = Field(None, ge=0)
    exclude_chains: bool = False
    two_pass_mode: bool = True
    worker_count: int = Field(5, ge=1, le=50)


class ScrapeJobOut(BaseModel):
    id: str
    workspace_id: str
    status: str
    niche_keywords: list[str]
    zip_codes: list[str]
    radius_miles: int
    min_rating: Optional[float] = None
    min_reviews: Optional[int] = None
    exclude_chains: bool
    two_pass_mode: bool
    worker_count: int
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    records_found: int
    api_calls_made: int
    estimated_cost_usd: float
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


# ---------- Companies ----------
class CompanyOut(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    google_maps_url: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    primary_category: Optional[str] = None
    categories: Optional[list[str]] = None
    business_status: Optional[str] = None
    apollo_enriched_at: Optional[datetime] = None
    companyenrich_enriched_at: Optional[datetime] = None
    lead_score: Optional[int] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    is_archived: bool = False
    created_at: datetime
    contact_count: int = 0


class CompanyUpdate(BaseModel):
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    is_archived: Optional[bool] = None


class CompanyDetailsRequest(BaseModel):
    company_ids: list[str] = Field(..., min_length=1)


# ---------- Contacts ----------
class ContactOut(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    email_status: Optional[str] = None
    email_confidence: Optional[int] = None
    email_source: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    is_primary: bool = False
    validated_at: Optional[datetime] = None


# ---------- Settings ----------
class WorkspaceSettingsUpdate(BaseModel):
    apollo_api_key: Optional[str] = None
    companyenrich_api_key: Optional[str] = None
    email_bison_api_key: Optional[str] = None
    email_bison_base_url: Optional[str] = None
    email_bison_field_mapping: Optional[dict] = None
    validation_provider: Optional[str] = None
    neverbounce_api_key: Optional[str] = None
    zerobounce_api_key: Optional[str] = None
    millionverifier_api_key: Optional[str] = None
    reoon_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    mxtoolbox_api_key: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    default_title_filters: Optional[list[str]] = None
    default_contact_cap: Optional[int] = None
    auto_validate_after_enrich: Optional[bool] = None
    validation_staleness_days: Optional[int] = None


class GoogleApiKeyCreate(BaseModel):
    name: str
    key_value: str
    daily_quota: int = 40000


class GoogleApiKeyOut(BaseModel):
    id: str
    name: str
    daily_quota: int
    calls_today: int
    status: str
    last_used_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
