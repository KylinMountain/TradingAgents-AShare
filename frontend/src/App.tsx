import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import { SpeedInsights } from '@vercel/speed-insights/react'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Analysis from './pages/Analysis'
import Reports from './pages/Reports'
import Settings from './pages/Settings'
import Portfolio from './pages/Portfolio'
import TrackingBoard from './pages/TrackingBoard'
import Login from './pages/Login'
import Feedback from './pages/Feedback'
import { useAuthStore } from './stores/authStore'

const ONLINE_BASE = 'https://app.510168.xyz'

function ExternalRedirect({ to }: { to: string }) {
  window.location.href = to
  return null
}

function RequireAuth({ children }: { children: JSX.Element }) {
  const { user, hydrated, hydrate } = useAuthStore()

  useEffect(() => {
    if (!hydrated) void hydrate()
  }, [hydrated, hydrate])

  if (!hydrated) {
    return <div className="min-h-screen flex items-center justify-center text-slate-500">加载中...</div>
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return children
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/sponsor" element={<ExternalRedirect to={`${ONLINE_BASE}/sponsor`} />} />
        <Route path="/thanks" element={<ExternalRedirect to={`${ONLINE_BASE}/thanks`} />} />
        <Route
          path="*"
          element={
            <RequireAuth>
              <Layout>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/tracking-board" element={<TrackingBoard />} />
                  <Route path="/analysis" element={<Analysis />} />
                  <Route path="/reports" element={<Reports />} />
                  <Route path="/portfolio" element={<Portfolio />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="/feedback" element={<Feedback />} />
                </Routes>
              </Layout>
            </RequireAuth>
          }
        />
      </Routes>
      <SpeedInsights />
    </BrowserRouter>
  )
}

export default App
