import { useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ScrapeJob, ZipRow } from '@/types'
import clsx from 'clsx'

const US_STATES = [
  'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA',
  'KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
  'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
  'VA','WA','WV','WI','WY','DC',
]

function parseZipCodes(raw: string): string[] {
  return Array.from(
    new Set(
      raw
        .split(/[\s,;\n]+/)
        .map((s) => s.trim())
        .filter((s) => /^\d{5}$/.test(s)),
    ),
  )
}

export function ScrapePage() {
  const qc = useQueryClient()
  const [keywordInput, setKeywordInput] = useState('')
  const [keywords, setKeywords] = useState<string[]>([])
  const [zipInput, setZipInput] = useState('')
  const [radius, setRadius] = useState(10)
  const [minRating, setMinRating] = useState<number | ''>('')
  const [minReviews, setMinReviews] = useState<number | ''>('')
  const [excludeChains, setExcludeChains] = useState(false)
  const [twoPass, setTwoPass] = useState(true)
  const [stateToAdd, setStateToAdd] = useState<string>('')

  const zips = useMemo(() => parseZipCodes(zipInput), [zipInput])

  const jobs = useQuery({
    queryKey: ['scrape-jobs'],
    queryFn: () => api<ScrapeJob[]>('/api/scrape/jobs?limit=10'),
    refetchInterval: (q) => {
      const data = q.state.data as ScrapeJob[] | undefined
      const hasActive = data?.some((j) => j.status === 'queued' || j.status === 'running')
      return hasActive ? 3000 : false
    },
  })

  const createJob = useMutation({
    mutationFn: () =>
      api<ScrapeJob>('/api/scrape/jobs', {
        method: 'POST',
        body: JSON.stringify({
          niche_keywords: keywords,
          zip_codes: zips,
          radius_miles: radius,
          min_rating: minRating === '' ? null : minRating,
          min_reviews: minReviews === '' ? null : minReviews,
          exclude_chains: excludeChains,
          two_pass_mode: twoPass,
          worker_count: 1, // Phase 1 = single worker
        }),
      }),
    onSuccess: () => {
      toast.success('Scrape job started')
      void qc.invalidateQueries({ queryKey: ['scrape-jobs'] })
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to start job'),
  })

  async function addStateZips() {
    if (!stateToAdd) return
    try {
      const rows = await api<ZipRow[]>(`/api/zips?state=${stateToAdd}&limit=5000`)
      const existing = new Set(zips)
      const merged = [...zips]
      for (const r of rows) {
        if (!existing.has(r.zip)) merged.push(r.zip)
      }
      setZipInput(merged.join(', '))
      toast.success(`Added ${rows.length} zips from ${stateToAdd}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Lookup failed')
    }
  }

  function addKeyword() {
    const k = keywordInput.trim()
    if (!k) return
    if (!keywords.includes(k)) setKeywords([...keywords, k])
    setKeywordInput('')
  }

  const canLaunch = keywords.length > 0 && zips.length > 0 && !createJob.isPending

  return (
    <div className="p-6 space-y-6 max-w-6xl">
      <h1 className="text-2xl font-semibold">Search &amp; Scrape</h1>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="card space-y-4">
          <h2 className="font-medium">Target zip codes</h2>
          <div>
            <label className="label">Zip codes (paste, space/comma/newline-separated)</label>
            <textarea
              className="input min-h-[96px] font-mono text-xs"
              placeholder="90210, 10001&#10;33139"
              value={zipInput}
              onChange={(e) => setZipInput(e.target.value)}
            />
            <div className="text-xs text-slate-400 mt-1">
              {zips.length} valid zip{zips.length === 1 ? '' : 's'}
            </div>
          </div>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label className="label">Or add all zips in a state</label>
              <select
                className="input"
                value={stateToAdd}
                onChange={(e) => setStateToAdd(e.target.value)}
              >
                <option value="">Select state…</option>
                {US_STATES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <button className="btn-secondary" type="button" onClick={() => void addStateZips()}>
              Add
            </button>
          </div>
        </div>

        <div className="card space-y-4">
          <h2 className="font-medium">Niche keywords</h2>
          <div className="flex gap-2">
            <input
              className="input flex-1"
              placeholder="e.g. dentist, hvac, plumber"
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  addKeyword()
                }
              }}
            />
            <button type="button" className="btn-secondary" onClick={addKeyword}>Add</button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {keywords.map((k) => (
              <span key={k} className="badge bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">
                {k}
                <button
                  className="ml-1.5 text-indigo-300/60 hover:text-indigo-300"
                  onClick={() => setKeywords(keywords.filter((x) => x !== k))}
                >
                  ×
                </button>
              </span>
            ))}
            {keywords.length === 0 && <span className="text-xs text-slate-500">No keywords yet.</span>}
          </div>
        </div>
      </div>

      <div className="card space-y-4">
        <h2 className="font-medium">Filters</h2>
        <div className="grid md:grid-cols-4 gap-4">
          <div>
            <label className="label">Radius: {radius} mi</label>
            <input
              type="range"
              min={1}
              max={50}
              value={radius}
              onChange={(e) => setRadius(Number(e.target.value))}
              className="w-full"
            />
          </div>
          <div>
            <label className="label">Min rating</label>
            <select
              className="input"
              value={minRating}
              onChange={(e) => setMinRating(e.target.value === '' ? '' : Number(e.target.value))}
            >
              <option value="">Any</option>
              <option value={3}>3.0+</option>
              <option value={3.5}>3.5+</option>
              <option value={4}>4.0+</option>
              <option value={4.5}>4.5+</option>
            </select>
          </div>
          <div>
            <label className="label">Min reviews</label>
            <input
              type="number"
              min={0}
              className="input"
              value={minReviews}
              onChange={(e) => setMinReviews(e.target.value === '' ? '' : Number(e.target.value))}
            />
          </div>
          <div className="flex flex-col justify-end gap-2">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={excludeChains} onChange={(e) => setExcludeChains(e.target.checked)} />
              Exclude chains
            </label>
            <label className="flex items-center gap-2 text-sm" title="Skip Place Details calls now; fetch them later on-demand to save API cost">
              <input type="checkbox" checked={twoPass} onChange={(e) => setTwoPass(e.target.checked)} />
              Two-pass mode (save API cost)
            </label>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="text-sm text-slate-400">
          {keywords.length > 0 && zips.length > 0 ? (
            <>
              Will dispatch <b>{keywords.length * zips.length}</b> tasks
              ({keywords.length} keyword{keywords.length === 1 ? '' : 's'} × {zips.length} zip{zips.length === 1 ? '' : 's'}).
            </>
          ) : (
            <>Add at least one keyword and one zip code.</>
          )}
        </div>
        <button
          type="button"
          className="btn-primary"
          disabled={!canLaunch}
          onClick={() => createJob.mutate()}
        >
          {createJob.isPending ? 'Launching…' : 'Launch Scrape'}
        </button>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-medium">Recent jobs</h2>
          <button className="btn-ghost" onClick={() => jobs.refetch()}>Refresh</button>
        </div>
        {jobs.isLoading ? (
          <div className="text-sm text-slate-400">Loading…</div>
        ) : (jobs.data?.length ?? 0) === 0 ? (
          <div className="text-sm text-slate-500">No jobs yet.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-400 border-b border-slate-700">
              <tr>
                <th className="text-left py-2">Status</th>
                <th className="text-left">Keywords</th>
                <th className="text-left">Zips</th>
                <th className="text-right">Progress</th>
                <th className="text-right">Found</th>
                <th className="text-right">API calls</th>
                <th className="text-right">Cost</th>
                <th className="text-right">Started</th>
              </tr>
            </thead>
            <tbody>
              {jobs.data?.map((j) => (
                <tr key={j.id} className="border-b border-slate-800 last:border-0">
                  <td className="py-2">
                    <span className={clsx('badge', statusClass(j.status))}>{j.status}</span>
                  </td>
                  <td className="truncate max-w-[160px]">{j.niche_keywords.join(', ')}</td>
                  <td>{j.zip_codes.length}</td>
                  <td className="text-right">{j.completed_tasks}/{j.total_tasks}</td>
                  <td className="text-right">{j.records_found}</td>
                  <td className="text-right">{j.api_calls_made}</td>
                  <td className="text-right">${j.estimated_cost_usd.toFixed(2)}</td>
                  <td className="text-right text-xs text-slate-400">
                    {j.started_at ? new Date(j.started_at).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
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
