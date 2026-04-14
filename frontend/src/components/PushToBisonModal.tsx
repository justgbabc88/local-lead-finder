import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'

type Campaign = { id: string | number; name?: string; campaign_name?: string; status?: string }
type FieldMap = Record<string, string>

const DEFAULT_MAPPING: FieldMap = {
  first_name: 'contact.first_name',
  last_name: 'contact.last_name',
  email: 'contact.email',
  phone: 'contact.phone',
  title: 'contact.title',
  company: 'company.name',
  city: 'company.city',
  state: 'company.state',
  website: 'company.website',
}

type Props = {
  selectedCompanyIds: string[]
  onClose: () => void
}

export function PushToBisonModal({ selectedCompanyIds, onClose }: Props) {
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1)
  const [campaignId, setCampaignId] = useState<string>('')
  const [mapping, setMapping] = useState<FieldMap>(DEFAULT_MAPPING)
  const [excludeInvalid, setExcludeInvalid] = useState(true)
  const [contactIds, setContactIds] = useState<string[]>([])

  // Resolve contacts from selected companies.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const ids: string[] = []
      for (const id of selectedCompanyIds) {
        const d = await api<{ contacts: { id: string; email: string | null }[] }>(
          `/api/companies/${id}`,
        )
        for (const c of d.contacts) if (c.email) ids.push(c.id)
      }
      if (!cancelled) setContactIds(ids)
    })()
    return () => { cancelled = true }
  }, [selectedCompanyIds])

  const saved = useQuery({
    queryKey: ['bison-field-mapping'],
    queryFn: () => api<FieldMap>('/api/email-bison/field-mapping'),
  })
  useEffect(() => {
    if (saved.data && Object.keys(saved.data).length > 0) setMapping(saved.data)
  }, [saved.data])

  const campaigns = useQuery({
    queryKey: ['bison-campaigns'],
    queryFn: () => api<Campaign[]>('/api/email-bison/campaigns'),
    enabled: step >= 2,
  })

  const push = useMutation({
    mutationFn: () =>
      api<{ pushed: number; skipped_invalid: number; skipped_suppressed: number }>(
        '/api/email-bison/push',
        {
          method: 'POST',
          body: JSON.stringify({
            campaign_id: campaignId,
            campaign_name: campaigns.data?.find((c) => String(c.id) === campaignId)?.name,
            contact_ids: contactIds,
            field_mapping: mapping,
            exclude_invalid: excludeInvalid,
            save_mapping: true,
          }),
        },
      ),
    onSuccess: (res) => {
      toast.success(`Pushed ${res.pushed} contacts (${res.skipped_suppressed + res.skipped_invalid} skipped)`)
      setStep(4)
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Push failed'),
  })

  return (
    <div className="fixed inset-0 z-30 grid place-items-center bg-black/60 p-4">
      <div className="card w-full max-w-xl space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Push to Email Bison</h2>
          <button className="btn-ghost" onClick={onClose}>×</button>
        </div>

        {/* Stepper */}
        <div className="flex text-xs text-slate-400">
          {['Segment', 'Campaign', 'Fields', 'Done'].map((label, i) => (
            <div key={label} className={`flex-1 ${step > i ? 'text-indigo-400' : step === i + 1 ? 'text-slate-200' : ''}`}>
              {i + 1}. {label}
            </div>
          ))}
        </div>

        {step === 1 && (
          <div className="space-y-3 text-sm">
            <p>
              <b>{selectedCompanyIds.length}</b> companies selected ·{' '}
              <b>{contactIds.length}</b> contacts with emails.
            </p>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={excludeInvalid}
                onChange={(e) => setExcludeInvalid(e.target.checked)} />
              Exclude invalid emails (recommended)
            </label>
            <p className="text-xs text-slate-500">
              Suppression list is always applied regardless of this setting.
            </p>
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={onClose}>Cancel</button>
              <button className="btn-primary" disabled={contactIds.length === 0} onClick={() => setStep(2)}>
                Next
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3 text-sm">
            {campaigns.isLoading ? (
              <div className="text-slate-400">Loading campaigns…</div>
            ) : campaigns.error ? (
              <div className="text-rose-300">{(campaigns.error as Error).message}</div>
            ) : (
              <>
                <label className="label">Target campaign</label>
                <select className="input" value={campaignId} onChange={(e) => setCampaignId(e.target.value)}>
                  <option value="">Select campaign…</option>
                  {campaigns.data?.map((c) => (
                    <option key={String(c.id)} value={String(c.id)}>
                      {c.name ?? c.campaign_name ?? `Campaign ${c.id}`}
                    </option>
                  ))}
                </select>
              </>
            )}
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setStep(1)}>Back</button>
              <button className="btn-primary" disabled={!campaignId} onClick={() => setStep(3)}>
                Next
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-3 text-sm">
            <p className="text-slate-400">
              Map Email Bison merge fields to LocalLeadEngine fields. Sources:
              {' '}<code>contact.*</code> or <code>company.*</code> — or a literal string.
            </p>
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {Object.entries(mapping).map(([dest, src]) => (
                <div key={dest} className="grid grid-cols-2 gap-2 items-center">
                  <input className="input font-mono text-xs" value={dest} onChange={(e) => {
                    const next = { ...mapping }
                    delete next[dest]
                    next[e.target.value] = src
                    setMapping(next)
                  }} />
                  <input className="input font-mono text-xs" value={src} onChange={(e) => {
                    setMapping({ ...mapping, [dest]: e.target.value })
                  }} />
                </div>
              ))}
            </div>
            <button
              className="btn-ghost text-xs"
              onClick={() => setMapping({ ...mapping, [`custom_${Object.keys(mapping).length}`]: '' })}
            >
              + Add field
            </button>
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setStep(2)}>Back</button>
              <button className="btn-primary" disabled={push.isPending} onClick={() => push.mutate()}>
                {push.isPending ? 'Pushing…' : `Push ${contactIds.length} contacts`}
              </button>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-3 text-sm">
            <p className="text-emerald-300">
              ✓ Contacts pushed. Monitor replies on the Campaign Analytics page.
            </p>
            <div className="flex justify-end">
              <button className="btn-primary" onClick={onClose}>Done</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
