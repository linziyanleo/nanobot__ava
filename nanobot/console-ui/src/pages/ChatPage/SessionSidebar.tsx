import { Plus, MessageSquare, Trash2 } from 'lucide-react'
import { cn } from '../../lib/utils'
import type { SessionMeta } from './types'
import { formatTokenCount } from './utils'

interface SessionSidebarProps {
  sessions: SessionMeta[]
  activeSession: string
  isConsoleScene: boolean
  onSessionSelect: (filename: string) => void
  onCreateConsole: () => void
  onDeleteSession: (sessionId: string) => void
}

export function SessionSidebar({
  sessions,
  activeSession,
  isConsoleScene,
  onSessionSelect,
  onCreateConsole,
  onDeleteSession,
}: SessionSidebarProps) {
  return (
    <div className="w-64 shrink-0 bg-[var(--bg-secondary)] border-r border-[var(--border)] flex flex-col">
      {/* New console session button — always visible at top */}
      <div className="p-2 border-b border-[var(--border)]">
        <button
          onClick={onCreateConsole}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" /> New Chat
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {sessions.map((s) => (
          <div
            key={s.filename}
            className={cn(
              'flex items-center justify-between group px-3 py-2 rounded-lg text-sm cursor-pointer transition-colors',
              activeSession === s.filename
                ? 'bg-[var(--accent)]/10 text-[var(--accent)]'
                : 'text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]',
            )}
            onClick={() => onSessionSelect(s.filename)}
          >
            <div className="flex items-center gap-2 truncate min-w-0">
              <MessageSquare className="w-3.5 h-3.5 shrink-0" />
              <div className="truncate">
                <div className="truncate text-sm">{s.key}</div>
                <div className="text-[10px] text-[var(--text-secondary)] opacity-70">
                  {formatTokenCount(s.token_stats.total_tokens)} tokens · {s.token_stats.llm_calls} calls
                </div>
              </div>
            </div>
            {isConsoleScene && (
              <button
                onClick={(e) => { e.stopPropagation(); onDeleteSession(s.filename) }}
                className="opacity-0 group-hover:opacity-100 p-1 text-[var(--text-secondary)] hover:text-[var(--danger)] transition-opacity shrink-0"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
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
