-- Phase 5 — workspace-level Email Bison base URL + saved field mapping.

alter table workspace_settings
  add column if not exists email_bison_base_url text,
  add column if not exists email_bison_field_mapping jsonb;
