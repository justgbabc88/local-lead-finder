import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { useAuth } from '@/hooks/useAuth'
import { WorkspaceProvider, useWorkspace } from '@/hooks/useWorkspace'
import { Layout } from '@/components/Layout'
import { LoginPage } from '@/pages/LoginPage'
import { SignupPage } from '@/pages/SignupPage'
import { WorkspaceBootstrapPage } from '@/pages/WorkspaceBootstrapPage'
import { ScrapePage } from '@/pages/ScrapePage'
import { LeadsPage } from '@/pages/LeadsPage'
import { SettingsPage } from '@/pages/SettingsPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 15_000,
    },
  },
})

function ProtectedRoutes() {
  const { session, loading: authLoading } = useAuth()
  const { active, workspaces, loading: wsLoading } = useWorkspace()

  if (authLoading) return <FullPageLoader />
  if (!session) return <Navigate to="/login" replace />
  if (wsLoading) return <FullPageLoader />
  if (workspaces.length === 0) return <Navigate to="/bootstrap" replace />
  if (!active) return <FullPageLoader />

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/scrape" replace />} />
        <Route path="/scrape" element={<ScrapePage />} />
        <Route path="/leads" element={<LeadsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/scrape" replace />} />
      </Route>
    </Routes>
  )
}

function FullPageLoader() {
  return (
    <div className="min-h-screen grid place-items-center text-slate-400">
      Loading…
    </div>
  )
}

function AppRoutes() {
  const { session, loading } = useAuth()
  if (loading) return <FullPageLoader />

  return (
    <Routes>
      <Route path="/login" element={session ? <Navigate to="/scrape" replace /> : <LoginPage />} />
      <Route path="/signup" element={session ? <Navigate to="/scrape" replace /> : <SignupPage />} />
      <Route path="/bootstrap" element={<WorkspaceBootstrapPage />} />
      <Route path="*" element={<ProtectedRoutes />} />
    </Routes>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <WorkspaceProvider>
          <AppRoutes />
        </WorkspaceProvider>
      </BrowserRouter>
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: '#1e293b',
            color: '#f1f5f9',
            border: '1px solid #334155',
          },
        }}
      />
    </QueryClientProvider>
  )
}
