import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { GoogleApiKey, WorkspaceSettings } from '@/types'

export function SettingsPage() {
  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <GoogleKeysCard />
      <ThirdPartyKeysCard />
      <IntegrationsCard />
      <EnrichmentDefaultsCard />
    </div>
  )
}

// ---------- Google API key pool ----------

function GoogleKeysCard() {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [value, setValue] = useState('')
  const [quota, setQuota] = useState(40000)

  const list = useQuery({
    queryKey: ['google-keys'],
    queryFn: () => api<GoogleApiKey[]>('/api/settings/google-keys'),
  })

  const add = useMutation({
    mutationFn: () =>
      api<GoogleApiKey>('/api/settings/google-keys', {
        method: 'POST',
        body: JSON.stringify({ name, key_value: value, daily_quota: quota }),
      }),
    onSuccess: () => {
      toast.success('Key added')
      setName(''); setValue(''); setQuota(40000)
      void qc.invalidateQueries({ queryKey: ['google-keys'] })
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Add failed'),
  })

  const del = useMutation({
    mutationFn: (id: string) => api(`/api/settings/google-keys/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['google-keys'] }),
  })

  return (
    <section className="card space-y-4">
      <div>
        <h2 className="font-medium">Google Places API keys</h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Phase 1 uses the backend&apos;s env key as a fallback. Keys added here are used
          by the Phase 2 worker pool. You can start adding them now.
        </p>
      </div>

      <div className="space-y-2">
        {list.isLoading ? (
          <div className="text-sm text-slate-400">Loading…</div>
        ) : (list.data?.length ?? 0) === 0 ? (
          <div className="text-sm text-slate-500">No keys yet.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-400 border-b border-slate-700">
              <tr>
                <th className="text-left py-2">Name</th>
                <th className="text-right">Calls today</th>
                <th className="text-right">Quota</th>
                <th className="text-left">Status</th>
                <th className="text-right">Added</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.data?.map((k) => (
                <tr key={k.id} className="border-b border-slate-800 last:border-0">
                  <td className="py-2">{k.name}</td>
                  <td className="text-right">{k.calls_today}</td>
                  <td className="text-right">{k.daily_quota}</td>
                  <td>{k.status}</td>
                  <td className="text-right text-xs text-slate-400">
                    {new Date(k.created_at).toLocaleDateString()}
                  </td>
                  <td className="text-right">
                    <button className="btn-ghost" onClick={() => del.mutate(k.id)}>Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="grid md:grid-cols-4 gap-3 items-end">
        <div className="md:col-span-1">
          <label className="label">Name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="md:col-span-2">
          <label className="label">Key value</label>
          <input className="input font-mono text-xs" value={value} onChange={(e) => setValue(e.target.value)} />
        </div>
        <div>
          <label className="label">Daily quota</label>
          <input
            type="number"
            className="input"
            value={quota}
            onChange={(e) => setQuota(Number(e.target.value))}
          />
        </div>
        <div className="md:col-span-4 flex justify-end">
          <button
            className="btn-primary"
            disabled={!name || !value || add.isPending}
            onClick={() => add.mutate()}
          >
            Add key
          </button>
        </div>
      </div>
    </section>
  )
}

// ---------- Third-party keys ----------

type SecretField = keyof WorkspaceSettings
const SECRET_FIELDS: { field: SecretField; setFlag: keyof WorkspaceSettings; label: string }[] = [
  { field: 'apollo_api_key' as SecretField, setFlag: 'apollo_api_key_set', label: 'Apollo API key' },
  { field: 'companyenrich_api_key' as SecretField, setFlag: 'companyenrich_api_key_set', label: 'CompanyEnrich API key' },
  { field: 'email_bison_api_key' as SecretField, setFlag: 'email_bison_api_key_set', label: 'Email Bison API key' },
  { field: 'neverbounce_api_key' as SecretField, setFlag: 'neverbounce_api_key_set', label: 'NeverBounce API key' },
  { field: 'zerobounce_api_key' as SecretField, setFlag: 'zerobounce_api_key_set', label: 'ZeroBounce API key' },
  { field: 'millionverifier_api_key' as SecretField, setFlag: 'millionverifier_api_key_set', label: 'MillionVerifier API key' },
  { field: 'reoon_api_key' as SecretField, setFlag: 'reoon_api_key_set', label: 'Reoon API key' },
  { field: 'anthropic_api_key' as SecretField, setFlag: 'anthropic_api_key_set', label: 'Anthropic API key' },
  { field: 'mxtoolbox_api_key' as SecretField, setFlag: 'mxtoolbox_api_key_set', label: 'MxToolbox API key' },
]

function ThirdPartyKeysCard() {
  const qc = useQueryClient()
  const settings = useQuery({
    queryKey: ['workspace-settings'],
    queryFn: () => api<WorkspaceSettings>('/api/settings'),
  })

  const [drafts, setDrafts] = useState<Record<string, string>>({})

  const save = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api<WorkspaceSettings>('/api/settings', { method: 'PATCH', body: JSON.stringify(payload) }),
    onSuccess: () => {
      toast.success('Saved')
      setDrafts({})
      void qc.invalidateQueries({ queryKey: ['workspace-settings'] })
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Save failed'),
  })

  return (
    <section className="card space-y-4">
      <div>
        <h2 className="font-medium">Third-party API keys</h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Used by enrichment, validation, and outreach. Most are only needed in Phase 3+.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        {SECRET_FIELDS.map(({ field, setFlag, label }) => {
          const isSet = Boolean(settings.data?.[setFlag])
          return (
            <div key={String(field)}>
              <label className="label">
                {label} {isSet && <span className="text-emerald-400">✓ set</span>}
              </label>
              <input
                className="input font-mono text-xs"
                placeholder={isSet ? '•••••• (stored)' : 'Paste key'}
                value={drafts[String(field)] ?? ''}
                onChange={(e) => setDrafts({ ...drafts, [String(field)]: e.target.value })}
              />
            </div>
          )
        })}
      </div>

      <div className="flex justify-end">
        <button
          className="btn-primary"
          disabled={Object.keys(drafts).length === 0 || save.isPending}
          onClick={() => {
            const payload: Record<string, string> = {}
            for (const [k, v] of Object.entries(drafts)) if (v) payload[k] = v
            save.mutate(payload)
          }}
        >
          Save keys
        </button>
      </div>
    </section>
  )
}

// ---------- Integrations: Email Bison base URL + Slack webhook ----------

function IntegrationsCard() {
  const qc = useQueryClient()
  const settings = useQuery({
    queryKey: ['workspace-settings'],
    queryFn: () => api<WorkspaceSettings & { email_bison_base_url?: string; slack_webhook_url?: string }>('/api/settings'),
  })
  const [baseUrl, setBaseUrl] = useState('')
  const [slack, setSlack] = useState('')
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    if (hydrated || !settings.data) return
    setBaseUrl(settings.data.email_bison_base_url ?? '')
    setSlack(settings.data.slack_webhook_url ?? '')
    setHydrated(true)
  }, [settings.data, hydrated])

  const save = useMutation({
    mutationFn: () =>
      api('/api/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          email_bison_base_url: baseUrl || null,
          slack_webhook_url: slack || null,
        }),
      }),
    onSuccess: () => {
      toast.success('Saved')
      void qc.invalidateQueries({ queryKey: ['workspace-settings'] })
    },
  })

  return (
    <section className="card space-y-4">
      <h2 className="font-medium">Integrations</h2>
      <div className="grid md:grid-cols-2 gap-3">
        <div>
          <label className="label">Email Bison base URL</label>
          <input className="input" placeholder="https://bison.yourdomain.com"
            value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
        </div>
        <div>
          <label className="label">Slack webhook URL (job alerts)</label>
          <input className="input" placeholder="https://hooks.slack.com/services/..."
            value={slack} onChange={(e) => setSlack(e.target.value)} />
        </div>
      </div>
      <div className="flex justify-end">
        <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>Save</button>
      </div>
    </section>
  )
}

// ---------- Enrichment defaults ----------

function EnrichmentDefaultsCard() {
  const qc = useQueryClient()
  const settings = useQuery({
    queryKey: ['workspace-settings'],
    queryFn: () => api<WorkspaceSettings>('/api/settings'),
  })

  const [titles, setTitles] = useState<string>('')
  const [cap, setCap] = useState<number>(3)
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    if (hydrated || !settings.data) return
    setTitles((settings.data.default_title_filters ?? []).join(', '))
    if (settings.data.default_contact_cap) setCap(settings.data.default_contact_cap)
    setHydrated(true)
  }, [settings.data, hydrated])

  const save = useMutation({
    mutationFn: () =>
      api<WorkspaceSettings>('/api/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          default_title_filters: titles
            .split(',').map((s) => s.trim()).filter(Boolean),
          default_contact_cap: cap,
        }),
      }),
    onSuccess: () => {
      toast.success('Saved')
      void qc.invalidateQueries({ queryKey: ['workspace-settings'] })
    },
  })

  return (
    <section className="card space-y-4">
      <h2 className="font-medium">Enrichment defaults</h2>
      <div className="grid md:grid-cols-2 gap-3">
        <div>
          <label className="label">Default title filters (comma-separated)</label>
          <input
            className="input"
            placeholder="owner, founder, ceo, president"
            value={titles}
            onChange={(e) => setTitles(e.target.value)}
          />
        </div>
        <div>
          <label className="label">Max contacts per company</label>
          <input
            type="number"
            min={1}
            max={20}
            className="input"
            value={cap}
            onChange={(e) => setCap(Number(e.target.value))}
          />
        </div>
      </div>
      <div className="flex justify-end">
        <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>
          Save
        </button>
      </div>
    </section>
  )
}
