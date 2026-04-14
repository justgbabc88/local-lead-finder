-- Phase 2 — concurrency primitives for the API key pool.
-- Workers call checkout_google_api_key() to atomically pick a key with remaining
-- quota and increment its counter in a single round-trip. This avoids the need
-- for Python-side row locking and plays nicely with dozens of parallel workers.

-- ---------- Checkout: atomic pick-and-increment ----------
create or replace function checkout_google_api_key(ws uuid)
returns table (id uuid, key_value text)
language plpgsql
as $$
declare
  picked uuid;
  picked_key text;
begin
  -- SELECT ... FOR UPDATE SKIP LOCKED picks a key no other txn is touching.
  select k.id, k.key_value
    into picked, picked_key
  from api_keys_google k
  where k.workspace_id = ws
    and k.status = 'active'
    and k.calls_today < k.daily_quota
  order by k.calls_today asc
  limit 1
  for update skip locked;

  if picked is null then
    return;
  end if;

  update api_keys_google
     set calls_today = calls_today + 1,
         last_used_at = now()
   where api_keys_google.id = picked;

  id := picked;
  key_value := picked_key;
  return next;
end;
$$;

-- ---------- Mark a key as rate-limited (worker calls this on 429) ----------
create or replace function flag_google_api_key(ws uuid, key_id uuid, new_status text, err text)
returns void
language sql
as $$
  update api_keys_google
     set status = new_status,
         last_error = err
   where workspace_id = ws and id = key_id;
$$;

-- ---------- Daily counter reset (called by health-check-cron) ----------
create or replace function reset_google_api_key_counters()
returns integer
language plpgsql
as $$
declare
  n integer;
begin
  update api_keys_google
     set calls_today = 0,
         quota_reset_at = now(),
         status = case when status = 'rate-limited' then 'active' else status end
   where status in ('active', 'rate-limited');
  get diagnostics n = row_count;
  return n;
end;
$$;

-- ---------- Atomic counter bumps for scrape_jobs ----------
-- Multiple workers finish tasks concurrently, so read-modify-write from Python
-- would lose increments. This function applies deltas atomically and flips the
-- job to 'complete' when the last task finishes.
create or replace function bump_scrape_job_counters(
  p_job_id uuid,
  p_completed int,
  p_failed int,
  p_records_found int,
  p_api_calls int
) returns table (
  total_tasks int,
  completed_tasks int,
  failed_tasks int,
  status text
) language plpgsql as $$
declare
  updated scrape_jobs%rowtype;
begin
  update scrape_jobs
     set completed_tasks = completed_tasks + p_completed,
         failed_tasks    = failed_tasks    + p_failed,
         records_found   = records_found   + p_records_found,
         api_calls_made  = api_calls_made  + p_api_calls
   where id = p_job_id
   returning * into updated;

  -- Last worker flips the job to complete (don't clobber a manual cancel).
  if updated.total_tasks > 0
     and (updated.completed_tasks + updated.failed_tasks) >= updated.total_tasks
     and updated.status in ('queued', 'running')
  then
    update scrape_jobs
       set status = 'complete',
           completed_at = now(),
           estimated_cost_usd = round((api_calls_made * 0.032)::numeric, 4)
     where id = p_job_id
     returning * into updated;
  end if;

  total_tasks     := updated.total_tasks;
  completed_tasks := updated.completed_tasks;
  failed_tasks    := updated.failed_tasks;
  status          := updated.status;
  return next;
end;
$$;

-- ---------- Grants (callable via supabase-py RPC as the service role) ----------
grant execute on function checkout_google_api_key(uuid) to service_role;
grant execute on function flag_google_api_key(uuid, uuid, text, text) to service_role;
grant execute on function reset_google_api_key_counters() to service_role;
grant execute on function bump_scrape_job_counters(uuid, int, int, int, int) to service_role;
