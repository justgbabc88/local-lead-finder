-- LocalLeadEngine — API key pool, enrichment/validation jobs,
-- templates, suppression, email bison exports, workspace settings.

-- ---------- Google API Key Pool ----------
create table if not exists api_keys_google (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references workspaces on delete cascade not null,
  name text not null,
  key_value text not null,
  daily_quota integer default 40000,
  calls_today integer default 0,
  quota_reset_at timestamptz,
  status text default 'active', -- active|paused|rate-limited|error
  last_used_at timestamptz,
  last_error text,
  created_at timestamptz default now()
);

create index if not exists idx_api_keys_google_workspace_status
  on api_keys_google(workspace_id, status);

-- ---------- Enrichment Jobs ----------
create table if not exists enrichment_jobs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references workspaces on delete cascade not null,
  provider text not null, -- apollo|companyenrich
  company_ids uuid[] not null,
  status text default 'queued',
  total_records integer,
  completed_records integer default 0,
  credits_used integer default 0,
  estimated_credits integer,
  error_message text,
  created_at timestamptz default now(),
  started_at timestamptz,
  completed_at timestamptz,
  created_by uuid references auth.users
);

create index if not exists idx_enrichment_jobs_workspace_status
  on enrichment_jobs(workspace_id, status);

-- ---------- Validation Jobs ----------
create table if not exists validation_jobs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references workspaces on delete cascade not null,
  provider text not null, -- neverbounce|zerobounce|millionverifier|reoon
  contact_ids uuid[] not null,
  status text default 'queued',
  total_emails integer,
  completed_emails integer default 0,
  valid_count integer default 0,
  invalid_count integer default 0,
  risky_count integer default 0,
  error_message text,
  created_at timestamptz default now(),
  completed_at timestamptz
);

create index if not exists idx_validation_jobs_workspace_status
  on validation_jobs(workspace_id, status);

-- ---------- Saved Search Templates ----------
create table if not exists search_templates (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references workspaces on delete cascade not null,
  name text not null,
  niche_keywords text[],
  zip_codes text[],
  filters jsonb,
  schedule_cron text,
  created_by uuid references auth.users,
  created_at timestamptz default now()
);

-- ---------- Suppression List ----------
create table if not exists suppression_list (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references workspaces on delete cascade not null,
  type text not null, -- email|domain
  value text not null,
  reason text,
  created_at timestamptz default now(),
  unique (workspace_id, type, value)
);

create index if not exists idx_suppression_list_workspace_value
  on suppression_list(workspace_id, value);

-- ---------- Email Bison Export Log ----------
create table if not exists email_bison_exports (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references workspaces on delete cascade not null,
  campaign_id text,
  campaign_name text,
  contact_ids uuid[],
  contact_count integer,
  field_mapping jsonb,
  status text default 'pending',
  error_message text,
  created_at timestamptz default now(),
  created_by uuid references auth.users
);

-- ---------- Workspace Settings ----------
create table if not exists workspace_settings (
  workspace_id uuid primary key references workspaces on delete cascade,
  -- API Keys (stored encrypted via Supabase Vault in production — plaintext for dev)
  apollo_api_key text,
  companyenrich_api_key text,
  email_bison_api_key text,
  validation_provider text default 'neverbounce',
  neverbounce_api_key text,
  zerobounce_api_key text,
  millionverifier_api_key text,
  reoon_api_key text,
  anthropic_api_key text,
  mxtoolbox_api_key text,
  slack_webhook_url text,
  -- Enrichment defaults
  default_title_filters text[],
  default_contact_cap integer default 3,
  auto_validate_after_enrich boolean default false,
  validation_staleness_days integer default 90,
  updated_at timestamptz default now()
);
