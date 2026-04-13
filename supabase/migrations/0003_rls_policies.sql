-- Row Level Security: restrict every business table to rows whose
-- workspace_id is in the current user's workspace membership.
-- us_zip_codes is public read; everything else is workspace-scoped.

-- Helper: is the caller a member of this workspace?
create or replace function is_workspace_member(ws uuid)
returns boolean language sql stable as $$
  select exists (
    select 1 from workspace_members
    where workspace_id = ws and user_id = auth.uid()
  );
$$;

-- ---------- Enable RLS ----------
alter table workspaces           enable row level security;
alter table workspace_members    enable row level security;
alter table us_zip_codes         enable row level security;
alter table scrape_jobs          enable row level security;
alter table companies            enable row level security;
alter table contacts             enable row level security;
alter table api_keys_google      enable row level security;
alter table enrichment_jobs      enable row level security;
alter table validation_jobs      enable row level security;
alter table search_templates     enable row level security;
alter table suppression_list     enable row level security;
alter table email_bison_exports  enable row level security;
alter table workspace_settings   enable row level security;

-- ---------- workspaces: members can see; owners can update/delete ----------
drop policy if exists workspaces_select on workspaces;
create policy workspaces_select on workspaces
  for select using (is_workspace_member(id));

drop policy if exists workspaces_insert on workspaces;
create policy workspaces_insert on workspaces
  for insert with check (owner_id = auth.uid());

drop policy if exists workspaces_update on workspaces;
create policy workspaces_update on workspaces
  for update using (owner_id = auth.uid());

drop policy if exists workspaces_delete on workspaces;
create policy workspaces_delete on workspaces
  for delete using (owner_id = auth.uid());

-- ---------- workspace_members ----------
drop policy if exists workspace_members_select on workspace_members;
create policy workspace_members_select on workspace_members
  for select using (is_workspace_member(workspace_id));

drop policy if exists workspace_members_insert on workspace_members;
create policy workspace_members_insert on workspace_members
  for insert with check (
    -- User can insert themselves as owner when they just created the workspace,
    -- or an existing owner can add others.
    user_id = auth.uid()
    or exists (
      select 1 from workspaces w
      where w.id = workspace_id and w.owner_id = auth.uid()
    )
  );

drop policy if exists workspace_members_delete on workspace_members;
create policy workspace_members_delete on workspace_members
  for delete using (
    exists (
      select 1 from workspaces w
      where w.id = workspace_id and w.owner_id = auth.uid()
    )
  );

-- ---------- us_zip_codes: public read for any authenticated user ----------
drop policy if exists us_zip_codes_select on us_zip_codes;
create policy us_zip_codes_select on us_zip_codes
  for select to authenticated using (true);

-- ---------- Generic workspace-scoped policies ----------
-- Apply the same read/write policy shape to every workspace-scoped table.

do $$
declare
  t text;
begin
  for t in
    select unnest(array[
      'scrape_jobs','companies','contacts','api_keys_google',
      'enrichment_jobs','validation_jobs','search_templates',
      'suppression_list','email_bison_exports','workspace_settings'
    ])
  loop
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
