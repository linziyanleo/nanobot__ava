import { useEffect, useState } from 'react'
import { ClipboardList, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '../api/client'

interface AuditEntry {
  ts: string
  user: string
  role: string
  action: string
  target: string
  detail: Record<string, unknown> | null
  ip: string
}

interface AuditResponse {
  entries: AuditEntry[]
  total: number
  page: number
  size: number
}

const ACTION_COLORS: Record<string, string> = {
  'auth.login': 'text-[var(--success)]',
  'auth.login_failed': 'text-[var(--danger)]',
  'config.update': 'text-[var(--accent)]',
  'file.update': 'text-[var(--accent)]',
  'gateway.restart': 'text-[var(--warning)]',
  'secret.reveal': 'text-[var(--danger)]',
  'user.create': 'text-purple-400',
  'user.update': 'text-purple-400',
  'user.delete': 'text-[var(--danger)]',
  'chat.send': 'text-[var(--text-secondary)]',
}

export default function AuditPage() {
  const [data, setData] = useState<AuditResponse | null>(null)
  const [page, setPage] = useState(1)
  const [filterUser, setFilterUser] = useState('')
  const [filterAction, setFilterAction] = useState('')

  const loadLogs = async () => {
    const params = new URLSearchParams({ page: String(page), size: '30' })
    if (filterUser) params.set('user', filterUser)
    if (filterAction) params.set('action', filterAction)
    const res = await api<AuditResponse>(`/audit/logs?${params}`)
    setData(res)
  }

  useEffect(() => { loadLogs() }, [page, filterUser, filterAction])

  const totalPages = data ? Math.ceil(data.total / data.size) : 0

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Audit Log</h1>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Filter by user"
            value={filterUser}
            onChange={(e) => { setFilterUser(e.target.value); setPage(1) }}
            className="px-3 py-1.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] text-sm text-[var(--text-primary)] w-36"
          />
          <select
            value={filterAction}
            onChange={(e) => { setFilterAction(e.target.value); setPage(1) }}
            className="px-3 py-1.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] text-sm text-[var(--text-primary)]"
          >
            <option value="">All actions</option>
            <option value="auth.login">auth.login</option>
            <option value="auth.login_failed">auth.login_failed</option>
            <option value="config.update">config.update</option>
            <option value="file.update">file.update</option>
            <option value="gateway.restart">gateway.restart</option>
            <option value="secret.reveal">secret.reveal</option>
            <option value="user.create">user.create</option>
            <option value="chat.send">chat.send</option>
          </select>
        </div>
      </div>

      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[var(--border)]">
              <th className="text-left px-5 py-3 text-xs font-medium text-[var(--text-secondary)] uppercase">Time</th>
              <th className="text-left px-5 py-3 text-xs font-medium text-[var(--text-secondary)] uppercase">User</th>
              <th className="text-left px-5 py-3 text-xs font-medium text-[var(--text-secondary)] uppercase">Action</th>
              <th className="text-left px-5 py-3 text-xs font-medium text-[var(--text-secondary)] uppercase">Target</th>
              <th className="text-left px-5 py-3 text-xs font-medium text-[var(--text-secondary)] uppercase">IP</th>
              <th className="text-left px-5 py-3 text-xs font-medium text-[var(--text-secondary)] uppercase">Detail</th>
            </tr>
          </thead>
          <tbody>
            {data?.entries.map((entry, i) => (
              <tr key={i} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-tertiary)]/50">
                <td className="px-5 py-3 text-xs text-[var(--text-secondary)] whitespace-nowrap">
                  {new Date(entry.ts).toLocaleString()}
                </td>
                <td className="px-5 py-3 text-sm font-medium">{entry.user}</td>
                <td className="px-5 py-3 text-sm">
                  <span className={`font-mono text-xs ${ACTION_COLORS[entry.action] || 'text-[var(--text-secondary)]'}`}>
                    {entry.action}
                  </span>
                </td>
                <td className="px-5 py-3 text-sm text-[var(--text-secondary)] max-w-[200px] truncate">{entry.target}</td>
                <td className="px-5 py-3 text-xs text-[var(--text-secondary)] font-mono">{entry.ip || '-'}</td>
                <td className="px-5 py-3 text-xs text-[var(--text-secondary)] max-w-[200px] truncate">
                  {entry.detail ? JSON.stringify(entry.detail) : '-'}
                </td>
              </tr>
            ))}
            {data?.entries.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-[var(--text-secondary)]">
                  <ClipboardList className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  No audit entries found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-[var(--text-secondary)]">
            {data?.total} entries total
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="p-2 rounded-lg bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-30"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-sm">Page {page} of {totalPages}</span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="p-2 rounded-lg bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-30"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
