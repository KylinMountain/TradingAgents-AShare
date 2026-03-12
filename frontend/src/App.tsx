import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Analysis from './pages/Analysis'
import Reports from './pages/Reports'
import Settings from './pages/Settings'
import Portfolio from './pages/Portfolio'
import Backtest from './pages/Backtest'
import Login from './pages/Login'
import { useAuthStore } from './stores/authStore'

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
        <Route
          path="*"
          element={
            <RequireAuth>
              <Layout>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/analysis" element={<Analysis />} />
                  <Route path="/reports" element={<Reports />} />
                  <Route path="/portfolio" element={<Portfolio />} />
                  <Route path="/backtest" element={<Backtest />} />
                  <Route path="/settings" element={<Settings />} />
                </Routes>
              </Layout>
            </RequireAuth>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
