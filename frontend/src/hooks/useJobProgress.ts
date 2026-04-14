import { useEffect, useRef, useState } from 'react'
import type { RealtimeChannel } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase'
import type { Company, ScrapeJob } from '@/types'

/**
 * Subscribe to a single scrape_jobs row + any companies inserted for that job.
 * Returns the latest job state and a ring buffer of the last N inserted companies.
 */
export function useJobProgress(jobId: string | null, opts: { feedSize?: number } = {}) {
  const feedSize = opts.feedSize ?? 10
  const [job, setJob] = useState<ScrapeJob | null>(null)
  const [feed, setFeed] = useState<Pick<Company, 'id' | 'name' | 'city' | 'state' | 'created_at'>[]>([])
  const channelRef = useRef<RealtimeChannel | null>(null)

  useEffect(() => {
    setJob(null)
    setFeed([])
    if (!jobId) return

    const channel = supabase
      .channel(`scrape-job-${jobId}`)
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'scrape_jobs', filter: `id=eq.${jobId}` },
        (payload) => setJob(payload.new as ScrapeJob),
      )
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'companies', filter: `scrape_job_id=eq.${jobId}` },
        (payload) => {
          const c = payload.new as Company
          setFeed((prev) =>
            [
              { id: c.id, name: c.name, city: c.city ?? null, state: c.state ?? null, created_at: c.created_at },
              ...prev,
            ].slice(0, feedSize),
          )
        },
      )
      .subscribe()

    channelRef.current = channel
    return () => {
      void supabase.removeChannel(channel)
      channelRef.current = null
    }
  }, [jobId, feedSize])

  return { job, feed }
}

/** Subscribe to ALL new companies in the active workspace (for lead-table tail). */
export function useNewCompanies(workspaceId: string | null, opts: { size?: number } = {}) {
  const size = opts.size ?? 20
  const [recent, setRecent] = useState<Company[]>([])

  useEffect(() => {
    setRecent([])
    if (!workspaceId) return
    const channel = supabase
      .channel(`companies-${workspaceId}`)
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'companies', filter: `workspace_id=eq.${workspaceId}` },
        (payload) => {
          const c = payload.new as Company
          setRecent((prev) => [c, ...prev].slice(0, size))
        },
      )
      .subscribe()
    return () => {
      void supabase.removeChannel(channel)
    }
  }, [workspaceId, size])

  return recent
}
