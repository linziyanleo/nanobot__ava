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
      label: '网关状态',
      value: status?.running ? '运行中' : '未运行',
      sub: status?.running ? `PID: ${status.pid} | 运行时间: ${formatUptime(status.uptime_seconds)}` : '',
      color: status?.running ? 'text-[var(--success)]' : 'text-[var(--danger)]',
      onClick: () => navigate('/gateway'),
    },
    {
      icon: Settings,
      label: '配置',
      value: '管理',
      sub: '编辑配置',
      color: 'text-[var(--accent)]',
      onClick: () => navigate('/config'),
    },
    {
      icon: FileText,
      label: '文件',
      value: '浏览',
      sub: '工作空间 & 记忆文件',
      color: 'text-[var(--warning)]',
      onClick: () => navigate('/files'),
    },
    {
      icon: MessageSquare,
      label: '聊天',
      value: '开始',
      sub: '测试 Agent 对话',
      color: 'text-purple-400',
      onClick: () => navigate('/chat'),
    },
  ];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">控制台</h1>
        <p className="text-[var(--text-secondary)] text-sm mt-1">欢迎回来, {user?.username}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {cards.map(card => (
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
          <h2 className="text-sm font-semibold">快速信息</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-[var(--text-secondary)]">角色</p>
            <p className="font-medium capitalize">{user?.role}</p>
          </div>
          <div>
            <p className="text-[var(--text-secondary)]">网关端口</p>
            <p className="font-medium">{status?.gateway_port ?? '—'}</p>
          </div>
          <div>
            <p className="text-[var(--text-secondary)]">控制台端口</p>
            <p className="font-medium">{status?.console_port ?? '—'}</p>
          </div>
          <div>
            <p className="text-[var(--text-secondary)]">状态</p>
            <p className={`font-medium ${status?.running ? 'text-[var(--success)]' : 'text-[var(--danger)]'}`}>
              {status?.running ? '在线' : '离线'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
