import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { api } from '@/lib/api'

type Summary = Record<string, number>

const STATUS_ORDER = ['valid', 'catch-all', 'risky', 'unknown', 'invalid', 'unvalidated'] as const

export function ValidationPage() {
  const qc = useQueryClient()
  const summary = useQuery({
    queryKey: ['validation-summary'],
    queryFn: () => api<Summary>('/api/validation/summary'),
    refetchInterval: 5000,
  })

  const restale = useMutation({
    mutationFn: () => api<{ queued: number }>('/api/validation/restale', { method: 'POST' }),
    onSuccess: (res) => {
      toast.success(`Queued ${res.queued} stale contacts`)
      void qc.invalidateQueries({ queryKey: ['validation-summary'] })
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed'),
  })

  const total = Object.values(summary.data ?? {}).reduce((a, b) => a + b, 0)

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-2xl font-semibold">Email Validation</h1>

      <div className="card">
        <h2 className="font-medium mb-4">Status breakdown</h2>
        {total === 0 ? (
          <div className="text-sm text-slate-500">No contacts with emails yet.</div>
        ) : (
          <div className="space-y-3">
            {STATUS_ORDER.map((status) => {
              const n = summary.data?.[status] ?? 0
              const pct = total > 0 ? Math.round((n / total) * 100) : 0
              return (
                <div key={status}>
                  <div className="flex justify-between text-xs text-slate-300 mb-1">
                    <span className="capitalize">{status.replace('-', ' ')}</span>
                    <span>{n.toLocaleString()} ({pct}%)</span>
                  </div>
                  <div className="h-2 bg-slate-700 rounded overflow-hidden">
                    <div className={`h-full ${barColor(status)}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div className="card space-y-3">
        <h2 className="font-medium">Re-validate stale contacts</h2>
        <p className="text-sm text-slate-400">
          Finds contacts whose last validation is older than the staleness window
          (configurable in Settings) and re-runs them through the active validator.
          Valid emails stay valid, but addresses that went invalid since the last
          check get automatically suppressed.
        </p>
        <button
          className="btn-primary"
          disabled={restale.isPending}
          onClick={() => restale.mutate()}
        >
          {restale.isPending ? 'Queuing…' : 'Run stale re-validation'}
        </button>
      </div>
    </div>
  )
}

function barColor(status: string): string {
  switch (status) {
    case 'valid': return 'bg-emerald-500'
    case 'catch-all': return 'bg-orange-400'
    case 'risky': return 'bg-amber-400'
    case 'unknown': return 'bg-slate-500'
    case 'invalid': return 'bg-rose-500'
    default: return 'bg-slate-600'
  }
}
