-- Phase 6 — bonus features schema.

-- 6e: scheduled scrape templates (schedule_cron already in 0002).

-- 6f: territory management — assign zips to specific users.
create table if not exists territories (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references workspaces on delete cascade not null,
  zip_code text not null,
  assigned_to uuid references auth.users,
  label text,
  created_at timestamptz default now(),
  unique(workspace_id, zip_code)
);
create index if not exists idx_territories_workspace on territories(workspace_id);

-- 6i: hygiene action log.
create table if not exists hygiene_log (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references workspaces on delete cascade not null,
  action text not null, -- flag_needs_enrichment | archive_closed
  company_id uuid references companies on delete set null,
  details jsonb,
  created_at timestamptz default now()
);

-- 6h: in-app notifications (job completion + domain alerts)
create table if not exists notifications (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references workspaces on delete cascade not null,
  type text not null, -- scrape_complete | enrichment_complete | validation_complete | domain_alert | hygiene
  title text not null,
  body text,
  link text,
  is_read boolean default false,
  created_at timestamptz default now()
);
create index if not exists idx_notifications_workspace_read
  on notifications(workspace_id, is_read, created_at desc);

-- 6b: lead scoring trigger (recompute on company insert/update)
create or replace function compute_lead_score(c companies) returns integer
language plpgsql immutable as $$
declare
  contact_count int;
  avg_confidence int;
  score int := 0;
begin
  -- These are cheap because they're called from a trigger; we accept that
  -- on UPDATE we re-read the live contact stats.
  select count(*), coalesce(avg(email_confidence)::int, 0)
    into contact_count, avg_confidence
    from contacts where company_id = c.id;

  score := score + least((coalesce(c.review_count, 0) / 50.0)::int, 20);
  score := score + (coalesce(c.rating, 0) / 5.0 * 20)::int;
  score := score + case when c.website is not null and length(c.website) > 0 then 15 else 0 end;
  score := score + least(contact_count * 5, 25);
  score := score + least(avg_confidence / 10, 10);
  score := score + case when c.apollo_enriched_at is not null then 10 else 0 end;

  return greatest(0, least(score, 100));
end;
$$;

create or replace function trg_lead_score_company() returns trigger
language plpgsql as $$
begin
  new.lead_score := compute_lead_score(new);
  return new;
end;
$$;

drop trigger if exists trg_companies_lead_score on companies;
create trigger trg_companies_lead_score
  before insert or update of rating, review_count, website, apollo_enriched_at, companyenrich_enriched_at
  on companies
  for each row execute function trg_lead_score_company();

-- Recompute parent company score when contacts change.
create or replace function trg_lead_score_contact() returns trigger
language plpgsql as $$
declare
  target uuid := coalesce(new.company_id, old.company_id);
  rec companies%rowtype;
begin
  if target is null then return coalesce(new, old); end if;
  select * into rec from companies where id = target;
  if found then
    update companies set lead_score = compute_lead_score(rec) where id = target;
  end if;
  return coalesce(new, old);
end;
$$;

drop trigger if exists trg_contacts_lead_score on contacts;
create trigger trg_contacts_lead_score
  after insert or update or delete on contacts
  for each row execute function trg_lead_score_contact();

-- RLS for the new tables.
alter table territories    enable row level security;
alter table hygiene_log    enable row level security;
alter table notifications  enable row level security;

do $$
declare t text;
begin
  for t in select unnest(array['territories','hygiene_log','notifications']) loop
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
