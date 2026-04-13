import { Fragment, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, apiRaw } from '@/lib/api'
import type { Company } from '@/types'
import { CompanyDetailPanel } from '@/components/CompanyDetailPanel'
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
  const [filters, setFilters] = useState<Filters>(EMPTY)
  const [applied, setApplied] = useState<Filters>(EMPTY)
  const [page, setPage] = useState(1)
  const [expanded, setExpanded] = useState<string | null>(null)

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

  async function exportCsv() {
    const params = new URLSearchParams()
    if (applied.search) params.set('search', applied.search)
    if (applied.state) params.set('state', applied.state)
    if (applied.zip) params.set('zip', applied.zip)
    if (applied.minRating) params.set('min_rating', applied.minRating)
    if (applied.minReviews) params.set('min_reviews', applied.minReviews)

    const resp = await apiRaw(`/api/companies/export?${params.toString()}`)
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `companies-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Lead Database</h1>
        <button className="btn-secondary" onClick={() => void exportCsv()}>Export CSV</button>
      </div>

      <div className="card">
        <div className="grid md:grid-cols-5 gap-3">
          <div>
            <label className="label">Search</label>
            <input
              className="input"
              placeholder="Company name…"
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            />
          </div>
          <div>
            <label className="label">State</label>
            <input
              className="input"
              placeholder="CA"
              maxLength={2}
              value={filters.state}
              onChange={(e) => setFilters({ ...filters, state: e.target.value.toUpperCase() })}
            />
          </div>
          <div>
            <label className="label">Zip</label>
            <input
              className="input"
              placeholder="90210"
              value={filters.zip}
              onChange={(e) => setFilters({ ...filters, zip: e.target.value })}
            />
          </div>
          <div>
            <label className="label">Min rating</label>
            <input
              className="input"
              type="number"
              step="0.1"
              min={0}
              max={5}
              value={filters.minRating}
              onChange={(e) => setFilters({ ...filters, minRating: e.target.value })}
            />
          </div>
          <div>
            <label className="label">Min reviews</label>
            <input
              className="input"
              type="number"
              min={0}
              value={filters.minReviews}
              onChange={(e) => setFilters({ ...filters, minReviews: e.target.value })}
            />
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
                <th className="text-left py-2">Company</th>
                <th className="text-left">Location</th>
                <th className="text-right">Rating</th>
                <th className="text-right">Reviews</th>
                <th className="text-left">Category</th>
                <th className="text-left">Phone</th>
                <th className="text-left">Website</th>
                <th className="text-right">Contacts</th>
                <th className="text-right">Score</th>
              </tr>
            </thead>
            <tbody>
              {list.data?.map((c) => (
                <Fragment key={c.id}>
                  <tr
                    className={clsx(
                      'border-b border-slate-800 cursor-pointer hover:bg-slate-800/50',
                      expanded === c.id && 'bg-slate-800/50',
                    )}
                    onClick={() => setExpanded(expanded === c.id ? null : c.id)}
                  >
                    <td className="py-2 font-medium">{c.name}</td>
                    <td className="text-slate-300">
                      {[c.city, c.state].filter(Boolean).join(', ')}
                    </td>
                    <td className="text-right">{c.rating?.toFixed(1) ?? '—'}</td>
                    <td className="text-right">{c.review_count ?? '—'}</td>
                    <td className="text-slate-300">{c.primary_category ?? '—'}</td>
                    <td className="text-slate-300">{c.phone ?? '—'}</td>
                    <td className="text-indigo-400 truncate max-w-[180px]">
                      {c.website ? (
                        <a
                          href={c.website}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {c.website.replace(/^https?:\/\//, '')}
                        </a>
                      ) : '—'}
                    </td>
                    <td className="text-right">{c.contact_count ?? 0}</td>
                    <td className="text-right">
                      {c.lead_score != null ? (
                        <span className={clsx('badge', scoreClass(c.lead_score))}>{c.lead_score}</span>
                      ) : '—'}
                    </td>
                  </tr>
                  {expanded === c.id && (
                    <tr>
                      <td colSpan={9} className="p-0 bg-slate-900/50 border-b border-slate-800">
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
    </div>
  )
}

function scoreClass(score: number) {
  if (score >= 60) return 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30'
  if (score >= 30) return 'bg-amber-500/10 text-amber-300 border border-amber-500/30'
  return 'bg-rose-500/10 text-rose-300 border border-rose-500/30'
}
