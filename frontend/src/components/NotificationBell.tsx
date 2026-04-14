import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'

type Notification = {
  id: string
  type: string
  title: string
  body: string | null
  link: string | null
  is_read: boolean
  created_at: string
}

export function NotificationBell() {
  const qc = useQueryClient()
  const nav = useNavigate()
  const [open, setOpen] = useState(false)

  const list = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api<Notification[]>('/api/notifications'),
    refetchInterval: 20_000,
  })
  const markRead = useMutation({
    mutationFn: (id: string) => api(`/api/notifications/${id}/read`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })
  const markAll = useMutation({
    mutationFn: () => api('/api/notifications/read-all', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })

  const unread = (list.data ?? []).filter((n) => !n.is_read).length

  return (
    <div className="relative">
      <button className="btn-ghost relative" onClick={() => setOpen(!open)} aria-label="Notifications">
        🔔
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 h-4 min-w-[1rem] px-1 text-[10px] flex items-center justify-center rounded-full bg-rose-500 text-white">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-slate-900 border border-slate-700 rounded shadow-xl z-40">
          <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700">
            <span className="text-sm font-medium">Notifications</span>
            {unread > 0 && (
              <button className="text-xs text-indigo-400 hover:underline" onClick={() => markAll.mutate()}>
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {list.data && list.data.length > 0 ? (
              list.data.map((n) => (
                <button
                  key={n.id}
                  className={`w-full text-left px-3 py-2 border-b border-slate-800 hover:bg-slate-800 ${
                    n.is_read ? 'text-slate-400' : 'text-slate-100'
                  }`}
                  onClick={() => {
                    markRead.mutate(n.id)
                    if (n.link) nav(n.link)
                    setOpen(false)
                  }}
                >
                  <div className="text-sm font-medium">{n.title}</div>
                  {n.body && <div className="text-xs text-slate-500 mt-0.5">{n.body}</div>}
                  <div className="text-[10px] text-slate-600 mt-1">
                    {new Date(n.created_at).toLocaleString()}
                  </div>
                </button>
              ))
            ) : (
              <div className="px-3 py-4 text-sm text-slate-500">No notifications</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
