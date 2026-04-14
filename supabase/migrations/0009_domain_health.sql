-- Domain Health Monitor — tables, RLS, helpers.

create table if not exists monitored_domains (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references workspaces on delete cascade not null,
  domain text not null,
  label text,
  dkim_selector text,
  health_score integer,
  last_checked_at timestamptz,
  check_frequency text default 'daily',
  alert_on_score_drop boolean default true,
  alert_threshold integer default 70,
  is_active boolean default true,
  created_at timestamptz default now(),
  unique (workspace_id, domain)
);
create index if not exists idx_monitored_domains_ws on monitored_domains(workspace_id);

create table if not exists domain_health_checks (
  id uuid primary key default gen_random_uuid(),
  domain_id uuid references monitored_domains on delete cascade not null,
  workspace_id uuid references workspaces on delete cascade not null,
  checked_at timestamptz default now(),

  spf_exists boolean, spf_record text, spf_status text,
  spf_issue text, spf_lookup_count integer,

  dkim_exists boolean, dkim_selector_used text, dkim_record text,
  dkim_status text, dkim_key_bits integer, dkim_issue text,

  dmarc_exists boolean, dmarc_record text, dmarc_policy text,
  dmarc_status text, dmarc_issue text,

  mx_exists boolean, mx_records jsonb, mx_status text, mx_issue text,

  blacklist_status text, blacklists_checked integer,
  blacklists_listed integer, blacklisted_on jsonb,

  domain_age_days integer, domain_registered_at timestamptz, domain_age_status text,

  a_record_exists boolean, dns_status text,

  overall_score integer, overall_status text, issues_count integer,
  raw_results jsonb
);
create index if not exists idx_dhc_domain on domain_health_checks(domain_id, checked_at desc);

create table if not exists domain_health_alerts (
  id uuid primary key default gen_random_uuid(),
  domain_id uuid references monitored_domains on delete cascade not null,
  workspace_id uuid references workspaces on delete cascade not null,
  alert_type text not null,
  message text,
  previous_score integer,
  new_score integer,
  is_resolved boolean default false,
  alerted_at timestamptz default now(),
  resolved_at timestamptz
);
create index if not exists idx_domain_alerts_ws on domain_health_alerts(workspace_id, is_resolved);

-- RLS
alter table monitored_domains     enable row level security;
alter table domain_health_checks  enable row level security;
alter table domain_health_alerts  enable row level security;

do $$
declare t text;
begin
  for t in select unnest(array['monitored_domains','domain_health_checks','domain_health_alerts']) loop
    execute format('drop policy if exists %I_select on %I;', t, t);
    execute format($f$create policy %I_select on %I
      for select using (is_workspace_member(workspace_id));$f$, t, t);
    execute format('drop policy if exists %I_insert on %I;', t, t);
    execute format($f$create policy %I_insert on %I
      for insert with check (is_workspace_member(workspace_id));$f$, t, t);
    execute format('drop policy if exists %I_update on %I;', t, t);
    execute format($f$create policy %I_update on %I
      for update using (is_workspace_member(workspace_id));$f$, t, t);
    execute format('drop policy if exists %I_delete on %I;', t, t);
    execute format($f$create policy %I_delete on %I
      for delete using (is_workspace_member(workspace_id));$f$, t, t);
  end loop;
end $$;
