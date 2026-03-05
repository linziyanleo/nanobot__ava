import { useEffect, useState, useCallback } from 'react'
import { Server, Settings, FileText, MessageSquare, Activity } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../stores/auth'
import { useNavigate } from 'react-router-dom'

interface GatewayStatusData {
  running: boolean
  pid: number | null
  uptime_seconds: number | null
  gateway_port: number | null
  console_port: number | null
}

export default function DashboardPage() {
  const [status, setStatus] = useState<GatewayStatusData | null>(null)
  const { user } = useAuth()
  const navigate = useNavigate()

  const loadStatus = useCallback(() => {
    api<GatewayStatusData>('/gateway/status').then(setStatus).catch(() => {})
  }, [])

  useEffect(() => {
    loadStatus()
    const interval = setInterval(loadStatus, 10000)
    return () => clearInterval(interval)
  }, [loadStatus])

  const formatUptime = (s: number | null) => {
    if (s == null) return 'N/A'
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    return h > 0 ? `${h}h ${m}m` : `${m}m`
  }

  const cards = [
    {
      icon: Server,
      label: 'Gateway Status',
      value: status?.running ? 'Running' : 'Stopped',
      sub: status?.running ? `PID: ${status.pid} | Uptime: ${formatUptime(status.uptime_seconds)}` : '',
      color: status?.running ? 'text-[var(--success)]' : 'text-[var(--danger)]',
      onClick: () => navigate('/gateway'),
    },
    {
      icon: Settings,
      label: 'Configuration',
      value: 'Manage',
      sub: 'Edit config files',
      color: 'text-[var(--accent)]',
      onClick: () => navigate('/config'),
    },
    {
      icon: FileText,
      label: 'Files',
      value: 'Browse',
      sub: 'Workspace & memory files',
      color: 'text-[var(--warning)]',
      onClick: () => navigate('/files'),
    },
    {
      icon: MessageSquare,
      label: 'Chat Test',
      value: 'Start',
      sub: 'Test agent conversations',
      color: 'text-purple-400',
      onClick: () => navigate('/chat'),
    },
  ]

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-[var(--text-secondary)] text-sm mt-1">
          Welcome back, {user?.username}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {cards.map((card) => (
          <button
            key={card.label}
            onClick={card.onClick}
            className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-5 text-left hover:border-[var(--accent)]/50 transition-all group"
          >
            <div className="flex items-center gap-3 mb-3">
              <div className={`p-2 rounded-lg bg-[var(--bg-tertiary)] ${card.color}`}>
                <card.icon className="w-5 h-5" />
              </div>
              <span className="text-sm text-[var(--text-secondary)]">{card.label}</span>
            </div>
            <p className={`text-xl font-semibold ${card.color}`}>{card.value}</p>
            {card.sub && <p className="text-xs text-[var(--text-secondary)] mt-1">{card.sub}</p>}
          </button>
        ))}
      </div>

      <div className="mt-8 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-3">
          <Activity className="w-4 h-4 text-[var(--accent)]" />
          <h2 className="text-sm font-semibold">Quick Info</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-[var(--text-secondary)]">Role</p>
            <p className="font-medium capitalize">{user?.role}</p>
          </div>
          <div>
            <p className="text-[var(--text-secondary)]">Gateway Port</p>
            <p className="font-medium">{status?.gateway_port ?? '—'}</p>
          </div>
          <div>
            <p className="text-[var(--text-secondary)]">Console Port</p>
            <p className="font-medium">{status?.console_port ?? '—'}</p>
          </div>
          <div>
            <p className="text-[var(--text-secondary)]">Status</p>
            <p className={`font-medium ${status?.running ? 'text-[var(--success)]' : 'text-[var(--danger)]'}`}>
              {status?.running ? 'Online' : 'Offline'}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
