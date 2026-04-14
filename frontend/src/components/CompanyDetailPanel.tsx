import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Company, Contact } from '@/types'

type CompanyDetail = Company & { contacts: Contact[] }

export function CompanyDetailPanel({ companyId }: { companyId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['company', companyId],
    queryFn: () => api<CompanyDetail>(`/api/companies/${companyId}`),
  })

  if (isLoading) return <div className="p-4 text-sm text-slate-400">Loading…</div>
  if (!data) return null

  return (
    <div className="p-4 space-y-4">
      <div className="grid md:grid-cols-3 gap-4 text-sm">
        <Field label="Address" value={data.address} />
        <Field label="Google Maps" value={data.google_maps_url} href={data.google_maps_url} />
        <Field label="Status" value={data.business_status} />
      </div>

      <div>
        <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">
          Contacts ({data.contacts.length})
        </div>
        {data.contacts.length === 0 ? (
          <div className="text-sm text-slate-500">
            No contacts yet. Enrichment lands in Phase 3.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-400 border-b border-slate-700">
              <tr>
                <th className="text-left py-1.5">Name</th>
                <th className="text-left">Title</th>
                <th className="text-left">Email</th>
                <th className="text-left">Status</th>
                <th className="text-left">Source</th>
              </tr>
            </thead>
            <tbody>
              {data.contacts.map((c) => (
                <tr key={c.id} className="border-b border-slate-800 last:border-0">
                  <td className="py-1.5">{c.full_name ?? [c.first_name, c.last_name].filter(Boolean).join(' ')}</td>
                  <td>{c.title ?? '—'}</td>
                  <td>{c.email ?? '—'}</td>
                  <td><StatusBadge status={c.email_status} /></td>
                  <td>{c.email_source ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status?: string | null }) {
  if (!status) return <span className="text-xs text-slate-600">—</span>
  const cls: Record<string, string> = {
    valid: 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30',
    'catch-all': 'bg-orange-500/10 text-orange-300 border border-orange-500/30',
    risky: 'bg-amber-500/10 text-amber-300 border border-amber-500/30',
    invalid: 'bg-rose-500/10 text-rose-300 border border-rose-500/30',
    unknown: 'bg-slate-500/10 text-slate-300 border border-slate-500/30',
    unvalidated: 'bg-slate-600/20 text-slate-400 border border-slate-700',
  }
  return <span className={`badge ${cls[status] ?? cls.unvalidated}`}>{status}</span>
}

function Field({ label, value, href }: { label: string; value?: string | null; href?: string | null }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-slate-200 truncate">
        {value ? (
          href ? (
            <a href={href} target="_blank" rel="noreferrer" className="text-indigo-400 hover:underline">
              {value}
            </a>
          ) : value
        ) : '—'}
      </div>
    </div>
  )
}
