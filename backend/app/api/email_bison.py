"""Email Bison integration endpoints — list campaigns, push contacts, analytics."""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, require_user
from app.api.envelope import ok
from app.db.supabase_client import get_supabase
from app.services.email_bison import EmailBisonClient, EmailBisonError, map_contact

router = APIRouter(prefix="/api/email-bison", tags=["email-bison"])


# ---------- Helpers ----------

def _client_for(workspace_id: str) -> EmailBisonClient:
    sb = get_supabase()
    res = sb.table("workspace_settings").select(
        "email_bison_base_url, email_bison_api_key",
    ).eq("workspace_id", workspace_id).single().execute()
    s = res.data or {}
    try:
        return EmailBisonClient(
            base_url=s.get("email_bison_base_url") or "",
            api_key=s.get("email_bison_api_key") or "",
        )
    except EmailBisonError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


def _suppressed_values(workspace_id: str) -> tuple[set[str], set[str]]:
    sb = get_supabase()
    res = sb.table("suppression_list").select("type,value").eq(
        "workspace_id", workspace_id,
    ).execute()
    emails: set[str] = set()
    domains: set[str] = set()
    for r in (res.data or []):
        if r["type"] == "email":
            emails.add((r["value"] or "").lower())
        elif r["type"] == "domain":
            domains.add((r["value"] or "").lower())
    return emails, domains


# ---------- Endpoints ----------

@router.get("/campaigns")
async def list_campaigns(user: CurrentUser = Depends(require_user)):
    client = _client_for(user.workspace_id)
    try:
        return ok(await client.list_campaigns())
    except EmailBisonError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))


@router.get("/analytics")
async def campaigns_analytics(user: CurrentUser = Depends(require_user)):
    """Fetch analytics for every Bison campaign (one call per campaign)."""
    client = _client_for(user.workspace_id)
    try:
        campaigns = await client.list_campaigns()
        results = []
        for c in campaigns:
            cid = c.get("id") or c.get("uuid") or c.get("campaign_id")
            if not cid:
                continue
            try:
                stats = await client.get_campaign_analytics(str(cid))
            except EmailBisonError:
                stats = {}
            results.append({
                "id": cid,
                "name": c.get("name") or c.get("campaign_name") or "(untitled)",
                "status": c.get("status"),
                "stats": stats,
            })
        return ok(results)
    except EmailBisonError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))


@router.get("/analytics/{campaign_id}")
async def single_campaign_analytics(campaign_id: str, user: CurrentUser = Depends(require_user)):
    client = _client_for(user.workspace_id)
    try:
        return ok(await client.get_campaign_analytics(campaign_id))
    except EmailBisonError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))


class PushRequest(BaseModel):
    campaign_id: str
    campaign_name: Optional[str] = None
    contact_ids: list[str] = Field(..., min_length=1, max_length=10_000)
    field_mapping: dict[str, str]
    exclude_invalid: bool = True
    save_mapping: bool = True


@router.post("/push")
async def push_to_campaign(
    body: PushRequest,
    user: CurrentUser = Depends(require_user),
):
    sb = get_supabase()

    contacts_res = sb.table("contacts").select("*").eq(
        "workspace_id", user.workspace_id,
    ).in_("id", body.contact_ids).execute()
    contacts = contacts_res.data or []
    if not contacts:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No matching contacts")

    company_ids = list({c["company_id"] for c in contacts if c.get("company_id")})
    companies_res = sb.table("companies").select("*").in_("id", company_ids).execute()
    companies_by_id = {c["id"]: c for c in (companies_res.data or [])}

    suppressed_emails, suppressed_domains = _suppressed_values(user.workspace_id)

    skipped_invalid = 0
    skipped_suppressed = 0
    skipped_no_email = 0
    mapped_payload: list[dict[str, Any]] = []

    for c in contacts:
        email = (c.get("email") or "").lower()
        if not email:
            skipped_no_email += 1
            continue
        if body.exclude_invalid and c.get("email_status") == "invalid":
            skipped_invalid += 1
            continue
        domain = email.split("@", 1)[-1]
        if email in suppressed_emails or domain in suppressed_domains:
            skipped_suppressed += 1
            continue

        company = companies_by_id.get(c.get("company_id") or "") or {}
        mapped_payload.append(map_contact(c, company, body.field_mapping))

    if not mapped_payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "All contacts were filtered out (suppressed/invalid)")

    client = _client_for(user.workspace_id)
    export_id: Optional[str] = None
    try:
        log = sb.table("email_bison_exports").insert({
            "workspace_id": user.workspace_id,
            "campaign_id": body.campaign_id,
            "campaign_name": body.campaign_name,
            "contact_ids": body.contact_ids,
            "contact_count": len(mapped_payload),
            "field_mapping": body.field_mapping,
            "status": "pending",
            "created_by": user.id,
        }).execute()
        export_id = (log.data or [{}])[0].get("id")

        await client.push_contacts(body.campaign_id, mapped_payload)

        if export_id:
            sb.table("email_bison_exports").update({"status": "complete"}).eq("id", export_id).execute()
    except EmailBisonError as e:
        if export_id:
            sb.table("email_bison_exports").update({
                "status": "error", "error_message": str(e),
            }).eq("id", export_id).execute()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))

    # Persist the mapping for next time, if requested.
    if body.save_mapping:
        sb.table("workspace_settings").upsert({
            "workspace_id": user.workspace_id,
            "email_bison_field_mapping": body.field_mapping,
        }, on_conflict="workspace_id").execute()

    return ok({
        "pushed": len(mapped_payload),
        "skipped_invalid": skipped_invalid,
        "skipped_suppressed": skipped_suppressed,
        "skipped_no_email": skipped_no_email,
        "export_id": export_id,
    })


@router.get("/field-mapping")
async def get_saved_mapping(user: CurrentUser = Depends(require_user)):
    sb = get_supabase()
    res = sb.table("workspace_settings").select("email_bison_field_mapping").eq(
        "workspace_id", user.workspace_id,
    ).single().execute()
    return ok((res.data or {}).get("email_bison_field_mapping") or {})
