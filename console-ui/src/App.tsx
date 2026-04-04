import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './stores/auth'
import Layout from './components/layout/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ConfigPage from './pages/ConfigPage'
import MemoryPage from './pages/MemoryPage'
import MediaPage from './pages/MediaPage'
import PersonaPage from './pages/PersonaPage'
import SkillsPage from './pages/SkillsPage'
import ChatPage from './pages/ChatPage'
import TokenStatsPage from './pages/TokenStatsPage'
import UsersPage from './pages/UsersPage'
import ScheduledTasksPage from './pages/ScheduledTasksPage'
import BgTasksPage from './pages/BgTasksPage'
import BrowserPage from './pages/BrowserPage'

function ProtectedRoute({ children, adminOnly = false }: { children: React.ReactNode; adminOnly?: boolean }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="min-h-screen flex items-center justify-center text-[var(--text-secondary)]">Loading...</div>
  if (!user) return <Navigate to="/login" replace />
  if (adminOnly && user.role !== 'admin') return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  const { checkAuth, user, loading } = useAuth()

  useEffect(() => {
    checkAuth()
  }, [])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={user && !loading ? <Navigate to="/" replace /> : <LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="config" element={<ConfigPage />} />
          <Route path="memory" element={<MemoryPage />} />
          <Route path="media" element={<MediaPage />} />
          <Route path="persona" element={<PersonaPage />} />
          <Route path="skills" element={<SkillsPage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="gateway" element={<Navigate to="/" replace />} />
          <Route path="tasks" element={<ScheduledTasksPage />} />
          <Route path="bg-tasks" element={<BgTasksPage />} />
          <Route path="tokens" element={<TokenStatsPage />} />
          <Route path="browser" element={<BrowserPage />} />
          <Route path="users" element={<ProtectedRoute adminOnly><UsersPage /></ProtectedRoute>} />
          {/* Legacy routes redirect */}
          <Route path="files" element={<Navigate to="/memory" replace />} />
          <Route path="audit" element={<Navigate to="/users" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
