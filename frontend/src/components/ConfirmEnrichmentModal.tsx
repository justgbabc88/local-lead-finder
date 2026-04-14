type Job = {
  id: string
  provider: 'apollo' | 'companyenrich'
  total_records: number
  estimated_credits: number
}

type Props = {
  job: Job
  onCancel: () => void
  onConfirm: () => void
  confirming: boolean
}

export function ConfirmEnrichmentModal({ job, onCancel, onConfirm, confirming }: Props) {
  const providerLabel = job.provider === 'apollo' ? 'Apollo' : 'CompanyEnrich'
  return (
    <div className="fixed inset-0 z-30 grid place-items-center bg-black/60 p-4">
      <div className="card w-full max-w-md space-y-4">
        <h2 className="text-lg font-semibold">Confirm enrichment</h2>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">Provider</span>
            <span className="font-medium">{providerLabel}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Companies</span>
            <span className="font-medium">{job.total_records}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Estimated credits</span>
            <span className="font-medium">~{job.estimated_credits}</span>
          </div>
        </div>
        <p className="text-xs text-slate-500">
          Credits are consumed from your {providerLabel} account. Contacts already on
          a company won&apos;t be duplicated.
        </p>
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onCancel} disabled={confirming}>
            Cancel
          </button>
          <button className="btn-primary" onClick={onConfirm} disabled={confirming}>
            {confirming ? 'Starting…' : 'Confirm & enrich'}
          </button>
        </div>
      </div>
    </div>
  )
}
