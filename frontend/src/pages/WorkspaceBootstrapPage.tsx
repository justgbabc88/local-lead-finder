import { useState } from 'react'
import toast from 'react-hot-toast'
import { useNavigate } from 'react-router-dom'
import { useWorkspace } from '@/hooks/useWorkspace'

export function WorkspaceBootstrapPage() {
  const { createWorkspace } = useWorkspace()
  const [name, setName] = useState('My Workspace')
  const [submitting, setSubmitting] = useState(false)
  const nav = useNavigate()

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    try {
      await createWorkspace(name)
      toast.success('Workspace created')
      nav('/scrape', { replace: true })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create workspace')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen grid place-items-center p-6">
      <form onSubmit={onSubmit} className="card w-full max-w-md space-y-4">
        <div>
          <h1 className="text-xl font-semibold">Create your workspace</h1>
          <p className="text-sm text-slate-400 mt-1">
            A workspace isolates your leads, API keys, and settings. You can invite
            teammates later.
          </p>
        </div>
        <div>
          <label className="label">Workspace name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <button type="submit" className="btn-primary w-full" disabled={submitting}>
          {submitting ? 'Creating...' : 'Create workspace'}
        </button>
      </form>
    </div>
  )
}
