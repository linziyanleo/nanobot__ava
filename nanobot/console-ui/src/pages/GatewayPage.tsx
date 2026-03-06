import { useEffect, useState } from 'react'
import { Server, RefreshCw, Power, AlertTriangle } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../stores/auth'

interface GatewayStatusData {
  running: boolean
  pid: number | null
  uptime_seconds: number | null
  gateway_port: number | null
  console_port: number | null
}

export default function GatewayPage() {
  const [status, setStatus] = useState<GatewayStatusData | null>(null)
  const [restarting, setRestarting] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const { isAdmin } = useAuth()

  const loadStatus = async () => {
    try {
      const s = await api<GatewayStatusData>('/gateway/status')
      setStatus(s)
    } catch {}
  }

  useEffect(() => {
    loadStatus()
    const interval = setInterval(loadStatus, 10000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (countdown <= 0) return
    const timer = setTimeout(() => setCountdown(countdown - 1), 1000)
    return () => clearTimeout(timer)
  }, [countdown])

  const handleRestart = async (force: boolean = false) => {
    if (!confirm(`重启网关${force ? ' (强制)' : ''}? 控制台将短暂断开连接。`)) return;
    setRestarting(true)
    setMessage(null)
    try {
      const delayMs = 5000
      await api('/gateway/restart', {
        method: 'POST',
        body: JSON.stringify({ delay_ms: delayMs, force }),
      })
      setCountdown(Math.ceil(delayMs / 1000) + 5)
      setMessage({ type: 'success', text: `网关重启将在 ${delayMs / 1000}s 后执行` });
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '重启失败' });
    } finally {
      setRestarting(false)
    }
  }

  const formatUptime = (s: number | null) => {
    if (s == null) return 'N/A'
    const d = Math.floor(s / 86400)
    const h = Math.floor((s % 86400) / 3600)
    const m = Math.floor((s % 3600) / 60)
    const parts = []
    if (d > 0) parts.push(`${d}d`)
    if (h > 0) parts.push(`${h}h`)
    parts.push(`${m}m`)
    return parts.join(' ')
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">网关</h1>
        <button
          onClick={loadStatus}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-sm"
        >
          <RefreshCw className="w-4 h-4" /> 刷新
        </button>
      </div>

      {message && (
        <div
          className={`mb-4 p-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-[var(--success)]/10 text-[var(--success)]' : 'bg-[var(--danger)]/10 text-[var(--danger)]'}`}
        >
          {message.text}
        </div>
      )}

      {countdown > 0 && (
        <div className="mb-4 p-4 rounded-xl bg-[var(--warning)]/10 border border-[var(--warning)]/20 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-[var(--warning)]" />
          <div>
            <p className="text-sm font-medium text-[var(--warning)]">网关重启中</p>
            <p className="text-xs text-[var(--text-secondary)]">预计将在 ~{countdown}s 后恢复。页面将自动重新连接。</p>
          </div>
        </div>
      )}

      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className={`p-3 rounded-xl ${status?.running ? 'bg-[var(--success)]/10' : 'bg-[var(--danger)]/10'}`}>
            <Server className={`w-8 h-8 ${status?.running ? 'text-[var(--success)]' : 'text-[var(--danger)]'}`} />
          </div>
          <div>
            <h2 className="text-xl font-semibold">{status?.running ? '网关运行中' : '网关未运行'}</h2>
            <p className="text-sm text-[var(--text-secondary)]">
              {status?.running ? `PID: ${status.pid}` : '未检测到'}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-[var(--bg-primary)] rounded-lg p-4">
            <p className="text-xs text-[var(--text-secondary)] mb-1">状态</p>
            <p
              className={`text-lg font-semibold ${status?.running ? 'text-[var(--success)]' : 'text-[var(--danger)]'}`}
            >
              {status?.running ? '在线' : '离线'}
            </p>
          </div>
          <div className="bg-[var(--bg-primary)] rounded-lg p-4">
            <p className="text-xs text-[var(--text-secondary)] mb-1">PID</p>
            <p className="text-lg font-semibold">{status?.pid ?? '-'}</p>
          </div>
          <div className="bg-[var(--bg-primary)] rounded-lg p-4">
            <p className="text-xs text-[var(--text-secondary)] mb-1">运行时间</p>
            <p className="text-lg font-semibold">{formatUptime(status?.uptime_seconds ?? null)}</p>
          </div>
        </div>

        {isAdmin() && (
          <div className="flex gap-3">
            <button
              onClick={() => handleRestart(false)}
              disabled={restarting}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--warning)] hover:bg-[var(--warning)]/80 text-black text-sm font-medium disabled:opacity-50"
            >
              <RefreshCw className="w-4 h-4" />
              {restarting ? 'Scheduling...' : 'Graceful Restart'}
            </button>
            <button
              onClick={() => handleRestart(true)}
              disabled={restarting}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--danger)] hover:bg-[var(--danger)]/80 text-white text-sm font-medium disabled:opacity-50"
            >
              <Power className="w-4 h-4" /> Force Restart
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
