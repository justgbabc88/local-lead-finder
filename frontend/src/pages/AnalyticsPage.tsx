import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

type CampaignRow = {
  id: string | number
  name: string
  status?: string
  stats?: {
    sent?: number
    delivered?: number
    opens?: number
    replies?: number
    bounces?: number
    unsubscribes?: number
    delivery_rate?: number
    open_rate?: number
    reply_rate?: number
    bounce_rate?: number
  }
}

export function AnalyticsPage() {
  const q = useQuery({
    queryKey: ['bison-analytics'],
    queryFn: () => api<CampaignRow[]>('/api/email-bison/analytics'),
  })

  return (
    <div className="p-6 space-y-4 max-w-6xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Campaign Analytics</h1>
        <button className="btn-secondary" onClick={() => q.refetch()}>Refresh</button>
      </div>

      <div className="card overflow-x-auto">
        {q.isLoading ? (
          <div className="p-3 text-sm text-slate-400">Loading…</div>
        ) : q.error ? (
          <div className="p-3 text-sm text-rose-300">{(q.error as Error).message}</div>
        ) : (q.data?.length ?? 0) === 0 ? (
          <div className="p-3 text-sm text-slate-500">No campaigns yet. Push some contacts first.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-400 border-b border-slate-700">
              <tr>
                <th className="text-left py-2">Campaign</th>
                <th className="text-right">Sent</th>
                <th className="text-right">Delivered %</th>
                <th className="text-right">Open %</th>
                <th className="text-right">Reply %</th>
                <th className="text-right">Bounce %</th>
                <th className="text-right">Unsubs</th>
              </tr>
            </thead>
            <tbody>
              {q.data?.map((c) => {
                const s = c.stats ?? {}
                return (
                  <tr key={String(c.id)} className="border-b border-slate-800 last:border-0">
                    <td className="py-2 font-medium">{c.name}</td>
                    <td className="text-right">{num(s.sent)}</td>
                    <td className="text-right">{pct(s.delivery_rate)}</td>
                    <td className="text-right">{pct(s.open_rate)}</td>
                    <td className="text-right">{pct(s.reply_rate)}</td>
                    <td className="text-right">{pct(s.bounce_rate)}</td>
                    <td className="text-right">{num(s.unsubscribes)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function num(v: number | undefined) { return v == null ? '—' : v.toLocaleString() }
function pct(v: number | undefined) { return v == null ? '—' : `${(v * 100).toFixed(1)}%` }
