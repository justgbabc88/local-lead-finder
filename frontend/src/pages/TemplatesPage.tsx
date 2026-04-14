import { useState } from 'react'
import toast from 'react-hot-toast'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

type Template = {
  id: string
  name: string
  niche_keywords: string[] | null
  zip_codes: string[] | null
  filters: Record<string, unknown> | null
  schedule_cron: string | null
  created_at: string
}

export function TemplatesPage() {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [keywords, setKeywords] = useState('')
  const [zips, setZips] = useState('')
  const [cron, setCron] = useState('')

  const list = useQuery({
    queryKey: ['templates'],
    queryFn: () => api<Template[]>('/api/templates'),
  })

  const save = useMutation({
    mutationFn: () =>
      api('/api/templates', {
        method: 'POST',
        body: JSON.stringify({
          name,
          niche_keywords: keywords.split(',').map((s) => s.trim()).filter(Boolean),
          zip_codes: zips.split(/[\s,;\n]+/).map((s) => s.trim()).filter((s) => /^\d{5}$/.test(s)),
          schedule_cron: cron || null,
          filters: {},
        }),
      }),
    onSuccess: () => {
      toast.success('Template saved')
      setName(''); setKeywords(''); setZips(''); setCron('')
      void qc.invalidateQueries({ queryKey: ['templates'] })
    },
  })
  const del = useMutation({
    mutationFn: (id: string) => api(`/api/templates/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates'] }),
  })

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-2xl font-semibold">Search Templates</h1>

      <section className="card space-y-3">
        <h2 className="font-medium">New template</h2>
        <div className="grid md:grid-cols-2 gap-3">
          <div>
            <label className="label">Name</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="label">Schedule (cron, optional — UTC)</label>
            <input className="input" placeholder="0 9 * * * (daily 9am UTC)"
              value={cron} onChange={(e) => setCron(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="label">Keywords (comma-separated)</label>
          <input className="input" value={keywords} onChange={(e) => setKeywords(e.target.value)} />
        </div>
        <div>
          <label className="label">Zip codes</label>
          <textarea className="input font-mono text-xs min-h-[64px]"
            value={zips} onChange={(e) => setZips(e.target.value)} />
        </div>
        <div className="flex justify-end">
          <button className="btn-primary" disabled={!name || save.isPending} onClick={() => save.mutate()}>
            Save template
          </button>
        </div>
      </section>

      <section className="card">
        <h2 className="font-medium mb-3">Saved</h2>
        {list.isLoading ? (
          <div className="text-sm text-slate-400">Loading…</div>
        ) : (list.data?.length ?? 0) === 0 ? (
          <div className="text-sm text-slate-500">No templates yet.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-xs uppercase text-slate-400 border-b border-slate-700">
              <tr>
                <th className="text-left py-2">Name</th>
                <th className="text-left">Keywords</th>
                <th className="text-right">Zips</th>
                <th className="text-left">Schedule</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.data?.map((t) => (
                <tr key={t.id} className="border-b border-slate-800 last:border-0">
                  <td className="py-2 font-medium">{t.name}</td>
                  <td className="truncate max-w-[200px]">{(t.niche_keywords ?? []).join(', ')}</td>
                  <td className="text-right">{(t.zip_codes ?? []).length}</td>
                  <td className="font-mono text-xs">{t.schedule_cron ?? '—'}</td>
                  <td className="text-right">
                    <button className="btn-ghost text-xs" onClick={() => del.mutate(t.id)}>
                      Delete
                    </button>
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
