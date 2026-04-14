-- Phase 4 — atomic counters for validation_jobs.
create or replace function bump_validation_job_counters(
  p_job_id uuid,
  p_completed int,
  p_valid int,
  p_invalid int,
  p_risky int
) returns void language plpgsql as $$
declare
  updated validation_jobs%rowtype;
begin
  update validation_jobs
     set completed_emails = completed_emails + p_completed,
         valid_count      = valid_count      + p_valid,
         invalid_count    = invalid_count    + p_invalid,
         risky_count      = risky_count      + p_risky
   where id = p_job_id
   returning * into updated;

  if updated.total_emails is not null
     and updated.completed_emails >= updated.total_emails
     and updated.status in ('queued', 'running')
  then
    update validation_jobs
       set status = 'complete',
           completed_at = now()
     where id = p_job_id;
  end if;
end;
$$;

grant execute on function bump_validation_job_counters(uuid, int, int, int, int) to service_role;
