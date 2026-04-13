import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, setActiveWorkspaceId } from '@/lib/api'
import type { Workspace } from '@/types'
import { useAuth } from './useAuth'

type Ctx = {
  workspaces: Workspace[]
  active: Workspace | null
  loading: boolean
  setActive: (id: string) => void
  refresh: () => Promise<void>
  createWorkspace: (name: string) => Promise<Workspace>
}

const WorkspaceContext = createContext<Ctx | null>(null)

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth()
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [active, setActiveState] = useState<Workspace | null>(null)
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    if (!session) {
      setWorkspaces([])
      setActiveState(null)
      setActiveWorkspaceId(null)
      return
    }
    setLoading(true)
    try {
      const list = await api<Workspace[]>('/api/workspaces')
      setWorkspaces(list)
      const storedId = localStorage.getItem('lle:workspace_id')
      const next = list.find((w) => w.id === storedId) ?? list[0] ?? null
      setActiveState(next)
      setActiveWorkspaceId(next?.id ?? null)
    } finally {
      setLoading(false)
    }
  }, [session])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const setActive = useCallback(
    (id: string) => {
      const next = workspaces.find((w) => w.id === id) ?? null
      setActiveState(next)
      setActiveWorkspaceId(next?.id ?? null)
    },
    [workspaces],
  )

  const createWorkspace = useCallback(async (name: string) => {
    const ws = await api<Workspace>('/api/workspaces', {
      method: 'POST',
      body: JSON.stringify({ name }),
    })
    setWorkspaces((prev) => [...prev, ws])
    setActiveState(ws)
    setActiveWorkspaceId(ws.id)
    return ws
  }, [])

  return (
    <WorkspaceContext.Provider value={{ workspaces, active, loading, setActive, refresh, createWorkspace }}>
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) throw new Error('useWorkspace must be used inside WorkspaceProvider')
  return ctx
}
