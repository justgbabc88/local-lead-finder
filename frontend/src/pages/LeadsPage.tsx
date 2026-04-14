import { Fragment, useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiRaw } from '@/lib/api'
import type { Company } from '@/types'
import { CompanyDetailPanel } from '@/components/CompanyDetailPanel'
import { ActionBar } from '@/components/ActionBar'
import { useNewCompanies } from '@/hooks/useJobProgress'
import { useWorkspace } from '@/hooks/useWorkspace'
import clsx from 'clsx'

type Filters = {
  search: string
  state: string
  zip: string
  minRating: string
  minReviews: string
}

const EMPTY: Filters = { search: '', state: '', zip: '', minRating: '', minReviews: '' }

export function LeadsPage() {
  const qc = useQueryClient()
  const { active } = useWorkspace()
  const [filters, setFilters] = useState<Filters>(EMPTY)
  const [applied, setApplied] = useState<Filters>(EMPTY)
  const [page, setPage] = useState(1)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())

  // Realtime: when new companies stream in during an active scrape, invalidate
  // the first-page query so the user sees them without hitting refresh.
  const live = useNewCompanies(active?.id ?? null, { size: 10 })
  useEffect(() => {
    if (live.length === 0 || page !== 1) return
    void qc.invalidateQueries({ queryKey: ['companies'] })
  }, [live.length, page, qc])

  const list = useQuery({
    queryKey: ['companies', applied, page],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set('page', String(page))
      params.set('page_size', '50')
      if (applied.search) params.set('search', applied.search)
      if (applied.state) params.set('state', applied.state)
      if (applied.zip) params.set('zip', applied.zip)
      if (applied.minRating) params.set('min_rating', applied.minRating)
      if (applied.minReviews) params.set('min_reviews', applied.minReviews)
      return api<Company[]>(`/api/companies?${params.toString()}`)
    },
    placeholderData: (prev) => prev,
  })

  const exportParams = useMemo(() => {
    const p: Record<string, string> = {}
    if (applied.search) p.search = applied.search
    if (applied.state) p.state = applied.state
    if (applied.zip) p.zip = applied.zip
    if (applied.minRating) p.min_rating = applied.minRating
    if (applied.minReviews) p.min_reviews = applied.minReviews
    return p
  }, [applied])

  const singleEnrich = useMutation({
    mutationFn: async (args: { companyId: string; provider: 'apollo' | 'companyenrich' }) => {
      const job = await api<{ id: string }>('/api/enrichment/jobs', {
        method: 'POST',
        body: JSON.stringify({ provider: args.provider, company_ids: [args.companyId] }),
      })
      return api(`/api/enrichment/jobs/${job.id}/run`, { method: 'POST' })
    },
    onSuccess: () => {
      toast.success('Enrichment queued')
      void qc.invalidateQueries({ queryKey: ['companies'] })
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed'),
  })

  function toggleOne(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }
  function toggleAll() {
    if (!list.data) return
    if (selected.size === list.data.length) setSelected(new Set())
    else setSelected(new Set(list.data.map((c) => c.id)))
  }

  async function exportCsv() {
    const resp = await apiRaw(`/api/companies/export?${new URLSearchParams(exportParams).toString()}`)
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `companies-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="p-6 pb-20 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Lead Database</h1>
          {live.length > 0 && (
            <span className="badge bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 animate-pulse">
              +{live.length} new
            </span>
          )}
        </div>
        <button className="btn-secondary" onClick={() => void exportCsv()}>Export CSV</button>
      </div>

      <div className="card">
        <div className="grid md:grid-cols-5 gap-3">
          <div>
            <label className="label">Search</label>
            <input className="input" placeholder="Company name…"
              value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} />
          </div>
          <div>
            <label className="label">State</label>
            <input className="input" placeholder="CA" maxLength={2}
              value={filters.state}
              onChange={(e) => setFilters({ ...filters, state: e.target.value.toUpperCase() })} />
          </div>
          <div>
            <label className="label">Zip</label>
            <input className="input" placeholder="90210"
              value={filters.zip} onChange={(e) => setFilters({ ...filters, zip: e.target.value })} />
          </div>
          <div>
            <label className="label">Min rating</label>
            <input className="input" type="number" step="0.1" min={0} max={5}
              value={filters.minRating}
              onChange={(e) => setFilters({ ...filters, minRating: e.target.value })} />
          </div>
          <div>
            <label className="label">Min reviews</label>
            <input className="input" type="number" min={0}
              value={filters.minReviews}
              onChange={(e) => setFilters({ ...filters, minReviews: e.target.value })} />
          </div>
        </div>
        <div className="flex gap-2 mt-3 justify-end">
          <button className="btn-ghost" onClick={() => { setFilters(EMPTY); setApplied(EMPTY); setPage(1) }}>
            Clear
          </button>
          <button className="btn-primary" onClick={() => { setApplied(filters); setPage(1) }}>
            Apply
          </button>
        </div>
      </div>

      <div className="card overflow-x-auto">
        {list.isLoading ? (
          <div className="text-sm text-slate-400 p-3">Loading…</div>
        ) : (list.data?.length ?? 0) === 0 ? (
          <div className="text-sm text-slate-500 p-3">
            No leads yet. Run a scrape job to populate.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-400 border-b border-slate-700">
              <tr>
                <th className="py-2 w-8">
                  <input
                    type="checkbox"
                    checked={list.data!.length > 0 && selected.size === list.data!.length}
                    onChange={toggleAll}
                  />
                </th>
                <th className="text-left">Company</th>
                <th className="text-left">Location</th>
                <th className="text-right">Rating</th>
                <th className="text-right">Reviews</th>
                <th className="text-left">Category</th>
                <th className="text-left">Phone</th>
                <th className="text-left">Website</th>
                <th className="text-right">Contacts</th>
                <th className="text-center">Enriched</th>
                <th className="text-right">Score</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.data?.map((c) => (
                <Fragment key={c.id}>
                  <tr
                    className={clsx(
                      'border-b border-slate-800 hover:bg-slate-800/50',
                      expanded === c.id && 'bg-slate-800/50',
                      selected.has(c.id) && 'bg-indigo-500/5',
                    )}
                  >
                    <td className="py-2" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selected.has(c.id)}
                        onChange={() => toggleOne(c.id)}
                      />
                    </td>
                    <td
                      className="py-2 font-medium cursor-pointer"
                      onClick={() => setExpanded(expanded === c.id ? null : c.id)}
                    >
                      {c.name}
                    </td>
                    <td className="text-slate-300">{[c.city, c.state].filter(Boolean).join(', ')}</td>
                    <td className="text-right">{c.rating?.toFixed(1) ?? '—'}</td>
                    <td className="text-right">{c.review_count ?? '—'}</td>
                    <td className="text-slate-300">{c.primary_category ?? '—'}</td>
                    <td className="text-slate-300">{c.phone ?? '—'}</td>
                    <td className="text-indigo-400 truncate max-w-[180px]">
                      {c.website ? (
                        <a href={c.website} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
                          {c.website.replace(/^https?:\/\//, '')}
                        </a>
                      ) : '—'}
                    </td>
                    <td className="text-right">{c.contact_count ?? 0}</td>
                    <td className="text-center">
                      <EnrichmentBadges c={c} />
                    </td>
                    <td className="text-right">
                      {c.lead_score != null ? (
                        <span className={clsx('badge', scoreClass(c.lead_score))}>{c.lead_score}</span>
                      ) : '—'}
                    </td>
                    <td className="text-right whitespace-nowrap">
                      <button
                        className="badge bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/20"
                        title="Enrich with Apollo"
                        disabled={singleEnrich.isPending}
                        onClick={(e) => {
                          e.stopPropagation()
                          singleEnrich.mutate({ companyId: c.id, provider: 'apollo' })
                        }}
                      >
                        A
                      </button>
                      <button
                        className="badge ml-1 bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/20"
                        title="Enrich with CompanyEnrich"
                        disabled={singleEnrich.isPending}
                        onClick={(e) => {
                          e.stopPropagation()
                          singleEnrich.mutate({ companyId: c.id, provider: 'companyenrich' })
                        }}
                      >
                        C
                      </button>
                    </td>
                  </tr>
                  {expanded === c.id && (
                    <tr>
                      <td colSpan={12} className="p-0 bg-slate-900/50 border-b border-slate-800">
                        <CompanyDetailPanel companyId={c.id} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-slate-400">
        <div>Page {page}</div>
        <div className="flex gap-2">
          <button className="btn-ghost" disabled={page === 1} onClick={() => setPage(page - 1)}>Prev</button>
          <button
            className="btn-ghost"
            disabled={(list.data?.length ?? 0) < 50}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      </div>

      <ActionBar
        selectedIds={Array.from(selected)}
        onClear={() => setSelected(new Set())}
        exportParams={exportParams}
      />
    </div>
  )
}

function EnrichmentBadges({ c }: { c: Company }) {
  return (
    <div className="flex items-center justify-center gap-0.5">
      {c.apollo_enriched_at ? (
        <span title={`Apollo ${new Date(c.apollo_enriched_at).toLocaleDateString()}`}
              className="badge bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">A</span>
      ) : null}
      {c.companyenrich_enriched_at ? (
        <span title={`CompanyEnrich ${new Date(c.companyenrich_enriched_at).toLocaleDateString()}`}
              className="badge bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">C</span>
      ) : null}
      {!c.apollo_enriched_at && !c.companyenrich_enriched_at && (
        <span className="text-xs text-slate-600">—</span>
      )}
    </div>
  )
}

function scoreClass(score: number) {
  if (score >= 60) return 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30'
  if (score >= 30) return 'bg-amber-500/10 text-amber-300 border border-amber-500/30'
  return 'bg-rose-500/10 text-rose-300 border border-rose-500/30'
}
