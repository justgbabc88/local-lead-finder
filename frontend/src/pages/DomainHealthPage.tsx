import { Fragment, useState } from 'react'
import toast from 'react-hot-toast'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import clsx from 'clsx'

type Domain = {
  id: string
  domain: string
  label: string | null
  dkim_selector: string | null
  health_score: number | null
  last_checked_at: string | null
  alert_on_score_drop: boolean
  alert_threshold: number
  is_active: boolean
  latest_check: LatestCheck | null
}

type LatestCheck = {
  overall_status: string | null
  spf_status: string | null
  dkim_status: string | null
  dmarc_status: string | null
  mx_status: string | null
  blacklist_status: string | null
  checked_at: string
}

type FullCheck = LatestCheck & {
  spf_record?: string | null
  spf_issue?: string | null
  spf_lookup_count?: number | null
  dkim_record?: string | null
  dkim_selector_used?: string | null
  dkim_key_bits?: number | null
  dkim_issue?: string | null
  dmarc_record?: string | null
  dmarc_policy?: string | null
  dmarc_issue?: string | null
  mx_records?: { priority: number; host: string }[] | null
  mx_issue?: string | null
  blacklists_listed?: number | null
  blacklists_checked?: number | null
  blacklisted_on?: string[] | null
  domain_age_days?: number | null
  domain_age_status?: string | null
  overall_score?: number | null
  issues_count?: number | null
}

type Alert = {
  id: string
  domain_id: string
  alert_type: string
  message: string
  previous_score: number | null
  new_score: number | null
  alerted_at: string
}

export function DomainHealthPage() {
  const qc = useQueryClient()
  const [adding, setAdding] = useState(false)
  const [newDomain, setNewDomain] = useState('')
  const [newSelector, setNewSelector] = useState('')
  const [selected, setSelected] = useState<string | null>(null)

  const list = useQuery({
    queryKey: ['domain-health'],
    queryFn: () => api<Domain[]>('/api/domain-health'),
    refetchInterval: 15_000,
  })
  const alerts = useQuery({
    queryKey: ['domain-alerts'],
    queryFn: () => api<Alert[]>('/api/domain-health/alerts'),
  })

  const add = useMutation({
    mutationFn: () =>
      api<Domain>('/api/domain-health', {
        method: 'POST',
        body: JSON.stringify({
          domain: newDomain,
          dkim_selector: newSelector || null,
        }),
      }),
    onSuccess: () => {
      toast.success('Domain added — first check queued')
      setAdding(false); setNewDomain(''); setNewSelector('')
      void qc.invalidateQueries({ queryKey: ['domain-health'] })
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed'),
  })
  const del = useMutation({
    mutationFn: (id: string) => api(`/api/domain-health/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['domain-health'] }),
  })
  const recheck = useMutation({
    mutationFn: (id: string) => api(`/api/domain-health/${id}/check`, { method: 'POST' }),
    onSuccess: () => toast.success('Re-check queued'),
  })
  const resolve = useMutation({
    mutationFn: (id: string) => api(`/api/domain-health/alerts/${id}/resolve`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['domain-alerts'] }),
  })

  return (
    <div className="p-6 space-y-6 max-w-6xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Domain Health Monitor</h1>
        <button className="btn-primary" onClick={() => setAdding(true)}>+ Add domain</button>
      </div>

      {alerts.data && alerts.data.length > 0 && (
        <section className="card border-rose-500/30 space-y-2">
          <h2 className="font-medium text-rose-300">🔴 Active alerts</h2>
          {alerts.data.map((a) => (
            <div key={a.id} className="flex items-center justify-between text-sm">
              <div>
                <b>{a.alert_type}</b> · {a.message}
              </div>
              <button className="btn-ghost text-xs" onClick={() => resolve.mutate(a.id)}>
                Resolve
              </button>
            </div>
          ))}
        </section>
      )}

      {adding && (
        <section className="card space-y-3">
          <h2 className="font-medium">Add sending domain</h2>
          <div className="grid md:grid-cols-2 gap-3">
            <div>
              <label className="label">Domain</label>
              <input className="input" placeholder="coldmail.io"
                value={newDomain} onChange={(e) => setNewDomain(e.target.value)} />
            </div>
            <div>
              <label className="label">DKIM selector (optional)</label>
              <input className="input" placeholder="google / s1 / k1"
                value={newSelector} onChange={(e) => setNewSelector(e.target.value)} />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button className="btn-ghost" onClick={() => setAdding(false)}>Cancel</button>
            <button className="btn-primary" disabled={!newDomain || add.isPending}
              onClick={() => add.mutate()}>Add & check now</button>
          </div>
        </section>
      )}

      <section className="card overflow-x-auto">
        {list.isLoading ? (
          <div className="p-3 text-sm text-slate-400">Loading…</div>
        ) : (list.data?.length ?? 0) === 0 ? (
          <div className="p-3 text-sm text-slate-500">No domains yet.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-xs uppercase text-slate-400 border-b border-slate-700">
              <tr>
                <th className="text-left py-2">Domain</th>
                <th className="text-right">Score</th>
                <th className="text-center">SPF</th>
                <th className="text-center">DKIM</th>
                <th className="text-center">DMARC</th>
                <th className="text-center">Blacklist</th>
                <th className="text-right">Last check</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.data?.map((d) => (
                <Fragment key={d.id}>
                  <tr className="border-b border-slate-800 hover:bg-slate-800/50 cursor-pointer"
                      onClick={() => setSelected(selected === d.id ? null : d.id)}>
                    <td className="py-2 font-medium">{d.domain}</td>
                    <td className="text-right">
                      <span className={clsx('badge', scoreClass(d.health_score))}>
                        {d.health_score ?? '—'}
                      </span>
                    </td>
                    <td className="text-center"><StatusIcon s={d.latest_check?.spf_status} /></td>
                    <td className="text-center"><StatusIcon s={d.latest_check?.dkim_status} /></td>
                    <td className="text-center"><StatusIcon s={d.latest_check?.dmarc_status} /></td>
                    <td className="text-center">
                      <StatusIcon s={d.latest_check?.blacklist_status === 'clean' ? 'pass' :
                                     d.latest_check?.blacklist_status === 'listed' ? 'fail' : null} />
                    </td>
                    <td className="text-right text-xs text-slate-400">
                      {d.last_checked_at ? new Date(d.last_checked_at).toLocaleString() : '—'}
                    </td>
                    <td className="text-right whitespace-nowrap">
                      <button className="btn-ghost text-xs" onClick={(e) => {
                        e.stopPropagation(); recheck.mutate(d.id)
                      }}>Re-check</button>
                      <button className="btn-ghost text-xs text-rose-400" onClick={(e) => {
                        e.stopPropagation(); del.mutate(d.id)
                      }}>Remove</button>
                    </td>
                  </tr>
                  {selected === d.id && (
                    <tr>
                      <td colSpan={8} className="p-0 bg-slate-900/50 border-b border-slate-800">
                        <DomainDetail domainId={d.id} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}

function DomainDetail({ domainId }: { domainId: string }) {
  const { data } = useQuery({
    queryKey: ['domain-health-latest', domainId],
    queryFn: () => api<FullCheck | null>(`/api/domain-health/${domainId}/history/latest`),
  })
  if (!data) return <div className="p-4 text-sm text-slate-500">No check results yet.</div>

  return (
    <div className="p-4 space-y-3 text-sm">
      <CheckRow label="SPF" status={data.spf_status ?? null}
        body={data.spf_record ?? undefined} issue={data.spf_issue ?? undefined}
        extra={data.spf_lookup_count != null ? `${data.spf_lookup_count}/10 lookups` : undefined} />
      <CheckRow label="DKIM" status={data.dkim_status ?? null}
        body={data.dkim_record ?? undefined} issue={data.dkim_issue ?? undefined}
        extra={[data.dkim_selector_used && `selector: ${data.dkim_selector_used}`,
                data.dkim_key_bits && `${data.dkim_key_bits}-bit key`]
               .filter(Boolean).join(' · ')} />
      <CheckRow label="DMARC" status={data.dmarc_status ?? null}
        body={data.dmarc_record ?? undefined} issue={data.dmarc_issue ?? undefined}
        extra={data.dmarc_policy ? `p=${data.dmarc_policy}` : undefined} />
      <CheckRow label="MX" status={data.mx_status ?? null}
        body={data.mx_records ? data.mx_records.map((m) => `${m.priority} ${m.host}`).join(', ') : undefined}
        issue={data.mx_issue ?? undefined} />
      <CheckRow label="Blacklist"
        status={data.blacklist_status === 'clean' ? 'pass' : data.blacklist_status === 'listed' ? 'fail' : null}
        body={data.blacklists_listed != null
          ? `${data.blacklists_listed}/${data.blacklists_checked ?? 0} blacklists`
          : undefined}
        issue={data.blacklisted_on && data.blacklisted_on.length > 0
          ? `Listed on: ${data.blacklisted_on.join(', ')}`
          : undefined} />
      <CheckRow label="Age" status={data.domain_age_status ?? null}
        body={data.domain_age_days != null ? `${data.domain_age_days} days old` : undefined} />
      {data.checked_at && (
        <div className="text-xs text-slate-500">
          Last checked {new Date(data.checked_at).toLocaleString()}
        </div>
      )}
    </div>
  )
}

function CheckRow({ label, status, body, issue, extra }:
    { label: string; status: string | null; body?: string; issue?: string; extra?: string }) {
  return (
    <div className="flex items-start gap-3 border-b border-slate-800 pb-2 last:border-0">
      <StatusIcon s={status} />
      <div className="font-medium w-20">{label}</div>
      <div className="flex-1 space-y-0.5">
        {body && <div className="font-mono text-xs text-slate-300 truncate">{body}</div>}
        {extra && <div className="text-xs text-slate-500">{extra}</div>}
        {issue && (
          <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded p-1.5 mt-1">
            {issue}
          </div>
        )}
      </div>
    </div>
  )
}

function StatusIcon({ s }: { s: string | null | undefined }) {
  if (s === 'pass') return <span className="text-emerald-400">✓</span>
  if (s === 'warning') return <span className="text-amber-400">⚠</span>
  if (s === 'fail') return <span className="text-rose-400">✗</span>
  return <span className="text-slate-600">—</span>
}

function scoreClass(score: number | null) {
  if (score == null) return 'bg-slate-600/30 text-slate-400 border border-slate-600'
  if (score >= 80) return 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30'
  if (score >= 50) return 'bg-amber-500/10 text-amber-300 border border-amber-500/30'
  return 'bg-rose-500/10 text-rose-300 border border-rose-500/30'
}
