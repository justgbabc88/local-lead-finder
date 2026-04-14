import { useMemo } from 'react'
import { useJobProgress } from '@/hooks/useJobProgress'
import type { ScrapeJob } from '@/types'
import clsx from 'clsx'

type Props = {
  initial: ScrapeJob
}

/** Live progress card for an active scrape — subscribes via Supabase Realtime. */
export function LiveJobCard({ initial }: Props) {
  const { job: live, feed } = useJobProgress(initial.id, { feedSize: 8 })
  const job = live ?? initial

  const pct = job.total_tasks > 0
    ? Math.round(((job.completed_tasks + job.failed_tasks) / job.total_tasks) * 100)
    : 0

  const eta = useMemo(() => {
    if (!job.started_at || job.status === 'complete' || job.completed_tasks === 0) return null
    const elapsedMs = Date.now() - new Date(job.started_at).getTime()
    const perTask = elapsedMs / job.completed_tasks
    const remaining = job.total_tasks - job.completed_tasks - job.failed_tasks
    if (remaining <= 0) return null
    const msLeft = remaining * perTask
    return formatDuration(msLeft)
  }, [job.started_at, job.completed_tasks, job.failed_tasks, job.total_tasks, job.status])

  return (
    <div className="card border-indigo-500/30 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-wide text-indigo-400">Live job</div>
          <div className="font-medium mt-0.5">
            {job.niche_keywords.slice(0, 3).join(', ')}
            {job.niche_keywords.length > 3 && ` +${job.niche_keywords.length - 3} more`}
            {' · '}
            {job.zip_codes.length} zip{job.zip_codes.length === 1 ? '' : 's'}
          </div>
        </div>
        <span className={clsx('badge', statusClass(job.status))}>{job.status}</span>
      </div>

      <div>
        <div className="flex justify-between text-xs text-slate-400 mb-1">
          <span>{job.completed_tasks}/{job.total_tasks} tasks</span>
          <span>
            {eta ? `ETA ${eta}` : job.status === 'complete' ? 'Done' : '—'}
          </span>
        </div>
        <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-indigo-500 transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 text-center">
        <Stat label="Found" value={job.records_found} accent="emerald" />
        <Stat label="API calls" value={job.api_calls_made} />
        <Stat label="Failed" value={job.failed_tasks} accent={job.failed_tasks > 0 ? 'rose' : undefined} />
        <Stat label="Cost" value={`$${job.estimated_cost_usd.toFixed(2)}`} />
      </div>

      {feed.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-400 mb-1.5">Latest finds</div>
          <ul className="text-sm space-y-0.5">
            {feed.map((c) => (
              <li key={c.id} className="flex justify-between gap-2 truncate">
                <span className="truncate text-slate-200">{c.name}</span>
                <span className="text-xs text-slate-500 shrink-0">
                  {[c.city, c.state].filter(Boolean).join(', ')}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {job.error_message && (
        <div className="text-xs text-rose-300 bg-rose-500/10 border border-rose-500/30 rounded p-2">
          {job.error_message}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: number | string; accent?: 'emerald' | 'rose' }) {
  return (
    <div>
      <div className={clsx(
        'text-lg font-semibold',
        accent === 'emerald' && 'text-emerald-300',
        accent === 'rose' && 'text-rose-300',
      )}>
        {value}
      </div>
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  )
}

function statusClass(status: ScrapeJob['status']) {
  switch (status) {
    case 'complete':
      return 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30'
    case 'running':
      return 'bg-indigo-500/10 text-indigo-300 border border-indigo-500/30'
    case 'queued':
      return 'bg-slate-600/30 text-slate-300 border border-slate-600/50'
    case 'error':
      return 'bg-rose-500/10 text-rose-300 border border-rose-500/30'
    case 'cancelled':
      return 'bg-amber-500/10 text-amber-300 border border-amber-500/30'
  }
}

function formatDuration(ms: number): string {
  if (ms < 60_000) return `${Math.round(ms / 1000)}s`
  const mins = Math.round(ms / 60_000)
  if (mins < 60) return `${mins}m`
  const hours = Math.floor(mins / 60)
  return `${hours}h ${mins % 60}m`
}
