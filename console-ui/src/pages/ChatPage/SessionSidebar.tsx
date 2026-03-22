import { useState } from 'react'
import { Plus, MessageSquare, Trash2, Pencil, Check, X } from 'lucide-react'
import { cn } from '../../lib/utils'
import type { SessionMeta } from './types'
import { formatTokenCount } from './utils'

interface SessionSidebarProps {
  sessions: SessionMeta[]
  activeSession: string
  isConsoleScene?: boolean
  onSessionSelect: (key: string) => void
  onCreateConsole: () => void
  onDeleteSession: (key: string) => void
  onRenameSession?: (key: string, newName: string) => void
}

export function SessionSidebar({
  sessions,
  activeSession,
  onSessionSelect,
  onCreateConsole,
  onDeleteSession,
  onRenameSession,
}: SessionSidebarProps) {
  const [editingFilename, setEditingFilename] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const startRename = (s: SessionMeta, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingFilename(s.key)
    setEditValue(s.key)
  }

  const confirmRename = (key: string) => {
    if (editValue.trim() && onRenameSession) {
      onRenameSession(key, editValue.trim())
    }
    setEditingFilename(null)
  }

  const cancelRename = () => setEditingFilename(null)

  return (
    <div className="w-64 shrink-0 bg-[var(--bg-secondary)] border-r border-[var(--border)] flex flex-col">
      <div className="p-2 border-b border-[var(--border)]">
        <button
          onClick={onCreateConsole}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" /> New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {sessions.map((s) => (
          <div
            key={s.key}
            className={cn(
              'flex items-center justify-between group px-3 py-2 rounded-lg text-sm cursor-pointer transition-colors',
              activeSession === s.key
                ? 'bg-[var(--accent)]/10 text-[var(--accent)]'
                : 'text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]',
            )}
            onClick={() => onSessionSelect(s.key)}
          >
            <div className="flex items-center gap-2 truncate min-w-0">
              <MessageSquare className="w-3.5 h-3.5 shrink-0" />
              {editingFilename === s.key ? (
                <div className="flex items-center gap-1 min-w-0" onClick={(e) => e.stopPropagation()}>
                  <input
                    autoFocus
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') confirmRename(s.key)
                      if (e.key === 'Escape') cancelRename()
                    }}
                    className="w-full px-1 py-0.5 text-sm bg-[var(--bg-primary)] border border-[var(--border)] rounded text-[var(--text-primary)] outline-none"
                  />
                  <button onClick={() => confirmRename(s.key)} className="p-0.5 text-green-500 hover:text-green-400">
                    <Check className="w-3 h-3" />
                  </button>
                  <button onClick={cancelRename} className="p-0.5 text-[var(--text-secondary)] hover:text-[var(--danger)]">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ) : (
                <div className="truncate">
                  <div className="truncate text-sm">{s.key}</div>
                  <div className="text-[10px] text-[var(--text-secondary)] opacity-70">
                    {formatTokenCount(s.token_stats.total_tokens)} tokens · {s.token_stats.llm_calls} calls
                  </div>
                </div>
              )}
            </div>
            {editingFilename !== s.key && confirmDelete !== s.key && (
              <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                {onRenameSession && (
                  <button
                    onClick={(e) => startRename(s, e)}
                    className="p-1 text-[var(--text-secondary)] hover:text-[var(--accent)]"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                )}
                <button
                  onClick={(e) => { e.stopPropagation(); setConfirmDelete(s.key) }}
                  className="p-1 text-[var(--text-secondary)] hover:text-[var(--danger)]"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
            {confirmDelete === s.key && (
              <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                <span className="text-[10px] text-[var(--danger)]">Delete?</span>
                <button
                  onClick={() => { onDeleteSession(s.key); setConfirmDelete(null) }}
                  className="p-0.5 text-[var(--danger)] hover:text-red-400"
                >
                  <Check className="w-3 h-3" />
                </button>
                <button
                  onClick={() => setConfirmDelete(null)}
                  className="p-0.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            )}
          </div>
        ))}
        {sessions.length === 0 && (
          <p className="text-center text-xs text-[var(--text-secondary)] py-8">
            No sessions
          </p>
        )}
      </div>
    </div>
  )
}
