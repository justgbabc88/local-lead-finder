import { supabase } from './supabase'

const BASE_URL = (import.meta.env.VITE_API_URL as string) ?? 'http://localhost:8000'

export type Envelope<T> = {
  data: T | null
  error: { code: string; message: string; details?: unknown } | null
  meta?: Record<string, unknown> | null
}

export class ApiError extends Error {
  code: string
  status: number
  details: unknown
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

/** Currently-selected workspace id (persisted). Set by the WorkspaceContext. */
let activeWorkspaceId: string | null =
  typeof window !== 'undefined' ? localStorage.getItem('lle:workspace_id') : null

export function setActiveWorkspaceId(id: string | null) {
  activeWorkspaceId = id
  if (typeof window !== 'undefined') {
    if (id) localStorage.setItem('lle:workspace_id', id)
    else localStorage.removeItem('lle:workspace_id')
  }
}

export function getActiveWorkspaceId() {
  return activeWorkspaceId
}

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  const h: Record<string, string> = {}
  if (token) h['Authorization'] = `Bearer ${token}`
  if (activeWorkspaceId) h['X-Workspace-Id'] = activeWorkspaceId
  return h
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = {
    'Content-Type': 'application/json',
    ...(await authHeaders()),
    ...(init.headers as Record<string, string> | undefined),
  }
  const resp = await fetch(`${BASE_URL}${path}`, { ...init, headers })

  // Export endpoints stream CSV — short-circuit before JSON parse
  const ctype = resp.headers.get('content-type') ?? ''
  if (!ctype.includes('application/json')) {
    if (!resp.ok) throw new ApiError(resp.status, 'http_error', await resp.text())
    return (await resp.blob()) as unknown as T
  }

  const body = (await resp.json()) as Envelope<T>
  if (!resp.ok || body.error) {
    const e = body.error ?? { code: 'http_error', message: `HTTP ${resp.status}` }
    throw new ApiError(resp.status, e.code, e.message, e.details)
  }
  return body.data as T
}

export async function apiRaw(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = { ...(await authHeaders()), ...(init.headers as Record<string, string> | undefined) }
  return fetch(`${BASE_URL}${path}`, { ...init, headers })
}
