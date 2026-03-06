import { useEffect, useRef } from 'react'
import { MessageSquare, Loader2 } from 'lucide-react'
import type { SessionMeta, TurnGroup } from './types'
import { SCENE_LABELS } from './types'
import { TurnGroupComponent } from './TurnGroup'
import { ChatInput } from './ChatInput'
import { formatTokenCount } from './utils'

interface MessageAreaProps {
  session: SessionMeta | null
  turns: TurnGroup[]
  loading: boolean
  isConsole: boolean
  streaming: string
  sending: boolean
  onSend: (message: string) => void
}

export function MessageArea({ session, turns, loading, isConsole, streaming, sending, onSend }: MessageAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const isInitialScroll = useRef(true)

  useEffect(() => {
    if (!bottomRef.current) return
    if (isInitialScroll.current) {
      bottomRef.current.scrollIntoView({ behavior: 'instant' })
      isInitialScroll.current = false
    } else {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [turns, streaming])

  useEffect(() => {
    isInitialScroll.current = true
  }, [session?.filename])

  if (!session) {
    return (
      <div className="flex-1 min-w-0 flex items-center justify-center text-[var(--text-secondary)] bg-[var(--bg-primary)]">
        <div className="text-center">
          <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>Select a session to view</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 min-w-0 flex flex-col bg-[var(--bg-primary)]">
      {/* Session header */}
      <div className="px-4 py-2.5 border-b border-[var(--border)] flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-[var(--text-primary)]">{session.key}</h3>
          <p className="text-[10px] text-[var(--text-secondary)]">
            {SCENE_LABELS[session.scene]}
            {' · '}
            {formatTokenCount(session.token_stats.total_tokens)} tokens
            {' · '}
            {session.token_stats.llm_calls} LLM calls
          </p>
        </div>
        {!isConsole && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">
            Read-only
          </span>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-4 space-y-4">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-[var(--accent)]" />
          </div>
        ) : (
          <>
            {turns.map((turn, i) => (
              <TurnGroupComponent key={i} turn={turn} />
            ))}
            {streaming && (
              <div className="flex justify-start">
                <div className="max-w-[80%] px-4 py-2.5 rounded-2xl rounded-bl-md bg-[var(--bg-secondary)] border border-[var(--border)] text-sm">
                  <pre className="whitespace-pre-wrap font-[inherit]">{streaming}</pre>
                  <span className="inline-block w-2 h-4 bg-[var(--accent)] animate-pulse ml-0.5" />
                </div>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input (console only) */}
      {isConsole && <ChatInput onSend={onSend} disabled={sending} />}
    </div>
  )
}
