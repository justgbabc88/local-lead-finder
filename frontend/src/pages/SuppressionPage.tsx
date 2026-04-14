import { useState } from 'react'
import toast from 'react-hot-toast'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

type Item = {
  id: string
  type: 'email' | 'domain'
  value: string
  reason: string | null
  created_at: string
}

export function SuppressionPage() {
  const qc = useQueryClient()
  const [raw, setRaw] = useState('')
  const [type, setType] = useState<'email' | 'domain'>('email')

  const list = useQuery({ queryKey: ['suppression'], queryFn: () => api<Item[]>('/api/suppression') })

  const add = useMutation({
    mutationFn: () =>
      api('/api/suppression', {
        method: 'POST',
        body: JSON.stringify({
          items: raw.split(/[\s,;\n]+/).map((v) => v.trim()).filter(Boolean)
            .map((value) => ({ type, value, reason: 'manual' })),
        }),
      }),
    onSuccess: () => {
      toast.success('Added')
      setRaw('')
      void qc.invalidateQueries({ queryKey: ['suppression'] })
    },
  })
  const del = useMutation({
    mutationFn: (id: string) => api(`/api/suppression/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['suppression'] }),
  })

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <h1 className="text-2xl font-semibold">Suppression List</h1>
      <p className="text-sm text-slate-400 -mt-3">
        Emails or domains here are excluded from Email Bison pushes and CSV
        exports. Invalid emails are auto-added after validation.
      </p>

      <section className="card space-y-3">
        <div className="grid md:grid-cols-4 gap-3">
          <div>
            <label className="label">Type</label>
            <select className="input" value={type} onChange={(e) => setType(e.target.value as 'email' | 'domain')}>
              <option value="email">Email</option>
              <option value="domain">Domain</option>
            </select>
          </div>
          <div className="md:col-span-3">
            <label className="label">Values (comma/newline-separated)</label>
            <textarea className="input font-mono text-xs min-h-[72px]"
              value={raw} onChange={(e) => setRaw(e.target.value)} />
          </div>
        </div>
        <div className="flex justify-end">
          <button className="btn-primary" disabled={!raw || add.isPending} onClick={() => add.mutate()}>
            Add to suppression
          </button>
        </div>
      </section>

      <section className="card">
        <h2 className="font-medium mb-3">Current ({list.data?.length ?? 0})</h2>
        {(list.data?.length ?? 0) === 0 ? (
          <div className="text-sm text-slate-500">Suppression list is empty.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-xs uppercase text-slate-400 border-b border-slate-700">
              <tr>
                <th className="text-left py-2">Type</th>
                <th className="text-left">Value</th>
                <th className="text-left">Reason</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.data?.map((i) => (
                <tr key={i.id} className="border-b border-slate-800 last:border-0">
                  <td className="py-2">{i.type}</td>
                  <td className="font-mono text-xs">{i.value}</td>
                  <td className="text-slate-400 text-xs">{i.reason ?? '—'}</td>
                  <td className="text-right">
                    <button className="btn-ghost text-xs" onClick={() => del.mutate(i.id)}>Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
