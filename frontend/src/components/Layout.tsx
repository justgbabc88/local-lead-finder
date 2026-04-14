import { NavLink, Outlet } from 'react-router-dom'
import { signOut } from '@/hooks/useAuth'
import { useWorkspace } from '@/hooks/useWorkspace'
import clsx from 'clsx'

const NAV = [
  { to: '/scrape', label: 'Search & Scrape' },
  { to: '/leads', label: 'Lead Database' },
  { to: '/validation', label: 'Validation' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/settings', label: 'Settings' },
]

export function Layout() {
  const { active, workspaces, setActive } = useWorkspace()

  return (
    <div className="flex h-screen">
      <aside className="w-60 shrink-0 bg-slate-950 border-r border-slate-800 flex flex-col">
        <div className="px-4 py-5 border-b border-slate-800">
          <div className="text-sm font-semibold tracking-wide text-indigo-400">
            LocalLeadEngine
          </div>
          <div className="text-xs text-slate-500 mt-0.5">Phase 1 · Core Scraper</div>
        </div>

        {workspaces.length > 1 && (
          <div className="px-3 py-3 border-b border-slate-800">
            <label className="label">Workspace</label>
            <select
              className="input"
              value={active?.id ?? ''}
              onChange={(e) => setActive(e.target.value)}
            >
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          </div>
        )}

        <nav className="flex-1 px-2 py-3 space-y-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  'block rounded px-3 py-2 text-sm',
                  isActive
                    ? 'bg-indigo-500/10 text-indigo-300'
                    : 'text-slate-300 hover:bg-slate-800',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-slate-800">
          {active && (
            <div className="text-xs text-slate-500 mb-2 truncate">
              {active.name}
            </div>
          )}
          <button
            className="btn-ghost w-full justify-start"
            onClick={() => void signOut()}
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
