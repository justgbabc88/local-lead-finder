-- LocalLeadEngine — core schema
-- Workspaces, membership, US zip codes, scrape jobs, companies, contacts.
-- All business tables carry workspace_id for multi-tenant isolation via RLS.

-- ---------- Extensions ----------
create extension if not exists "pgcrypto";

-- ---------- Workspaces ----------
create table if not exists workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  owner_id uuid references auth.users not null,
  created_at timestamptz default now()
);

create table if not exists workspace_members (
  workspace_id uuid references workspaces on delete cascade not null,
  user_id uuid references auth.users on delete cascade not null,
  role text default 'member', -- 'owner' | 'member'
  created_at timestamptz default now(),
  primary key (workspace_id, user_id)
);

create index if not exists idx_workspace_members_user on workspace_members(user_id);

-- ---------- US Zip Codes (preloaded ~42k rows) ----------
create table if not exists us_zip_codes (
  zip text primary key,
  city text,
  state text,
  state_abbr text,
  lat numeric,
  lng numeric,
  population integer
);

create index if not exists idx_us_zip_state on us_zip_codes(state_abbr);
create index if not exists idx_us_zip_city on us_zip_codes(lower(city));

-- ---------- Scrape Jobs ----------
create table if not exists scrape_jobs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references workspaces on delete cascade not null,
  status text default 'queued', -- queued|running|complete|error|cancelled
  niche_keywords text[] not null,
  zip_codes text[] not null,
  radius_miles integer default 10,
  min_rating numeric,
  min_reviews integer,
  exclude_chains boolean default false,
  worker_count integer default 5,
  two_pass_mode boolean default true,
  total_tasks integer default 0,
  completed_tasks integer default 0,
  failed_tasks integer default 0,
  records_found integer default 0,
  api_calls_made integer default 0,
  estimated_cost_usd numeric default 0,
  error_message text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz default now(),
  created_by uuid references auth.users
);

create index if not exists idx_scrape_jobs_workspace_status on scrape_jobs(workspace_id, status);
create index if not exists idx_scrape_jobs_created_at on scrape_jobs(created_at desc);

-- ---------- Companies ----------
create table if not exists companies (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references workspaces on delete cascade not null,
  place_id text not null,
  name text not null,
  address text,
  city text,
  state text,
  zip text,
  lat numeric,
  lng numeric,
  phone text,
  website text,
  google_maps_url text,
  rating numeric,
  review_count integer,
  primary_category text,
  categories text[],
  hours jsonb,
  price_level text,
  business_status text default 'OPERATIONAL',
  -- Enrichment state
  apollo_enriched_at timestamptz,
  companyenrich_enriched_at timestamptz,
  employee_count integer,
  revenue_estimate text,
  year_founded integer,
  tech_stack text[],
  linkedin_url text,
  facebook_url text,
  instagram_url text,
  -- Lead management
  lead_score integer,
  tags text[],
  notes text,
  is_archived boolean default false,
  -- Scrape source
  scrape_job_id uuid references scrape_jobs on delete set null,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (workspace_id, place_id)
);

create index if not exists idx_companies_workspace_zip on companies(workspace_id, zip);
create index if not exists idx_companies_workspace_state on companies(workspace_id, state);
create index if not exists idx_companies_workspace_category on companies(workspace_id, primary_category);
create index if not exists idx_companies_workspace_archived on companies(workspace_id, is_archived);
create index if not exists idx_companies_scrape_job on companies(scrape_job_id);
create index if not exists idx_companies_lead_score on companies(workspace_id, lead_score desc);

-- ---------- Contacts ----------
create table if not exists contacts (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references companies on delete cascade not null,
  workspace_id uuid references workspaces on delete cascade not null,
  first_name text,
  last_name text,
  full_name text,
  title text,
  seniority text,
  role_tag text,
  email text,
  email_status text, -- valid|risky|invalid|unknown|catch-all|unvalidated
  email_confidence integer,
  email_source text, -- apollo|companyenrich|website|gbp|pattern
  phone text,
  linkedin_url text,
  apollo_id text,
  is_primary boolean default false,
  notes text,
  tags text[],
  ai_opener text,
  validated_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists idx_contacts_company on contacts(company_id);
create index if not exists idx_contacts_email on contacts(email);
create index if not exists idx_contacts_workspace_status on contacts(workspace_id, email_status);

-- Prevent dup contacts with the same email at the same company
create unique index if not exists uq_contacts_company_email
  on contacts(company_id, lower(email))
  where email is not null;

-- ---------- Auto-update updated_at ----------
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end; $$;

drop trigger if exists trg_companies_updated on companies;
create trigger trg_companies_updated before update on companies
  for each row execute function set_updated_at();

drop trigger if exists trg_contacts_updated on contacts;
create trigger trg_contacts_updated before update on contacts
  for each row execute function set_updated_at();
