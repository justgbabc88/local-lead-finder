import { useState } from 'react'
import toast from 'react-hot-toast'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, apiRaw } from '@/lib/api'
import { ConfirmEnrichmentModal } from './ConfirmEnrichmentModal'

type Props = {
  selectedIds: string[]
  onClear: () => void
  exportParams: Record<string, string>
}

type ContactLite = { id: string; email: string | null }

type EnrichmentJob = {
  id: string
  provider: 'apollo' | 'companyenrich'
  total_records: number
  estimated_credits: number
}

export function ActionBar({ selectedIds, onClear, exportParams }: Props) {
  const qc = useQueryClient()
  const [pending, setPending] = useState<EnrichmentJob | null>(null)

  const createJob = useMutation({
    mutationFn: (provider: 'apollo' | 'companyenrich') =>
      api<EnrichmentJob>('/api/enrichment/jobs', {
        method: 'POST',
        body: JSON.stringify({ provider, company_ids: selectedIds }),
      }),
    onSuccess: (job) => setPending(job),
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed'),
  })

  const runJob = useMutation({
    mutationFn: (jobId: string) =>
      api(`/api/enrichment/jobs/${jobId}/run`, { method: 'POST' }),
    onSuccess: () => {
      toast.success('Enrichment started')
      setPending(null)
      onClear()
      void qc.invalidateQueries({ queryKey: ['companies'] })
      void qc.invalidateQueries({ queryKey: ['enrichment-jobs'] })
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to start'),
  })

  // Validate: fetch contacts across selected companies, then create a validation job.
  const validate = useMutation({
    mutationFn: async () => {
      // Pull contact lists per selected company — backend endpoint returns
      // the company detail (including contacts). Small N so sequential is fine.
      const contactIds: string[] = []
      for (const id of selectedIds) {
        const detail = await api<{ contacts: ContactLite[] }>(`/api/companies/${id}`)
        for (const c of detail.contacts) {
          if (c.email) contactIds.push(c.id)
        }
      }
      if (contactIds.length === 0) throw new Error('No emails in selection to validate')
      return api<{ total_emails: number }>('/api/validation/jobs', {
        method: 'POST',
        body: JSON.stringify({ contact_ids: contactIds }),
      })
    },
    onSuccess: (res) => {
      toast.success(`Validating ${res.total_emails} emails`)
      onClear()
      void qc.invalidateQueries({ queryKey: ['validation-summary'] })
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed'),
  })

  async function exportCsv() {
    const qs = new URLSearchParams(exportParams).toString()
    const resp = await apiRaw(`/api/companies/export?${qs}`)
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `companies-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (selectedIds.length === 0) return null

  return (
    <>
      <div className="fixed bottom-0 left-60 right-0 z-20 bg-slate-950 border-t border-slate-700 shadow-lg">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-3">
          <div className="text-sm">
            <b>{selectedIds.length}</b> selected
          </div>
          <div className="flex-1" />
          <button
            className="btn-primary bg-indigo-500/90 hover:bg-indigo-500"
            disabled={createJob.isPending}
            onClick={() => createJob.mutate('apollo')}
          >
            Enrich with Apollo
          </button>
          <button
            className="btn-primary bg-emerald-500/90 hover:bg-emerald-500"
            disabled={createJob.isPending}
            onClick={() => createJob.mutate('companyenrich')}
          >
            Enrich with CompanyEnrich
          </button>
          <button
            className="btn-primary bg-amber-500/90 hover:bg-amber-500"
            disabled={validate.isPending}
            onClick={() => validate.mutate()}
          >
            {validate.isPending ? 'Validating…' : 'Validate Emails'}
          </button>
          <button className="btn-secondary" onClick={() => void exportCsv()}>Export CSV</button>
          <button className="btn-ghost" onClick={onClear}>Clear</button>
        </div>
      </div>

      {pending && (
        <ConfirmEnrichmentModal
          job={pending}
          onCancel={() => setPending(null)}
          onConfirm={() => runJob.mutate(pending.id)}
          confirming={runJob.isPending}
        />
      )}
    </>
  )
}
