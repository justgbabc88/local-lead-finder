-- Phase 3 — atomic counters for enrichment_jobs.

create or replace function bump_enrichment_job_counters(
  p_job_id uuid,
  p_completed int,
  p_credits int
) returns table (
  status text,
  completed_records int,
  total_records int
) language plpgsql as $$
declare
  updated enrichment_jobs%rowtype;
begin
  update enrichment_jobs
     set completed_records = completed_records + p_completed,
         credits_used      = credits_used      + p_credits
   where id = p_job_id
   returning * into updated;

  if updated.total_records is not null
     and updated.completed_records >= updated.total_records
     and updated.status in ('queued', 'running')
  then
    update enrichment_jobs
       set status = 'complete',
           completed_at = now()
     where id = p_job_id
     returning * into updated;
  end if;

  status := updated.status;
  completed_records := updated.completed_records;
  total_records := updated.total_records;
  return next;
end;
$$;

grant execute on function bump_enrichment_job_counters(uuid, int, int) to service_role;
