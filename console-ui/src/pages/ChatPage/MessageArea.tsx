import { useEffect, useRef, useState, useCallback } from 'react'
import { MessageSquare, Loader2, Brain, ChevronDown, ChevronRight, RefreshCw, Copy, Check, ArrowDown, Search } from 'lucide-react'
import type { SessionMeta, TurnGroup, TurnTokenStats } from './types';
import { SCENE_LABELS } from './types'
import { TurnGroupComponent } from './TurnGroup'
import { ChatInput } from './ChatInput'
import { SearchModal } from './SearchModal'
import { formatTokenCount } from './utils'
import { api } from '../../api/client';

interface MessageAreaProps {
  session: SessionMeta | null
  turns: TurnGroup[]
  loading: boolean
  isConsole: boolean
  streaming: string
  thinkingStreaming: string
  sending: boolean
  onSend: (message: string) => void
  onRefresh: () => void
}

export function MessageArea({ session, turns, loading, isConsole, streaming, thinkingStreaming, sending, onSend, onRefresh }: MessageAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const isInitialScroll = useRef(true)
  const [thinkingExpanded, setThinkingExpanded] = useState(false)
  const [turnTokenStats, setTurnTokenStats] = useState<Map<number, TurnTokenStats>>(new Map());
  const [refreshing, setRefreshing] = useState(false)
  const [keyCopied, setKeyCopied] = useState(false)
  const [showScrollDown, setShowScrollDown] = useState(false)
  const [showSearch, setShowSearch] = useState(false)

  useEffect(() => {
    if (!session?.key) {
      setTurnTokenStats(new Map());
      return;
    }
    api<TurnTokenStats[]>(`/stats/tokens/by-session?session_key=${encodeURIComponent(session.key)}`)
      .then(data => {
        const map = new Map<number, TurnTokenStats>();
        for (const item of data) {
          if (item.turn_seq != null) map.set(item.turn_seq, item);
        }
        setTurnTokenStats(map);
      })
      .catch(() => setTurnTokenStats(new Map()));
  }, [session?.key, turns.length]);

  const checkScrollPosition = useCallback(() => {
    const el = scrollContainerRef.current
    if (!el) return
    const threshold = 100
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
    setShowScrollDown(!isAtBottom)
  }, [])

  useEffect(() => {
    const el = scrollContainerRef.current
    if (!el) return
    el.addEventListener('scroll', checkScrollPosition)
    return () => el.removeEventListener('scroll', checkScrollPosition)
  }, [checkScrollPosition])

  useEffect(() => {
    if (isInitialScroll.current && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'instant' })
      isInitialScroll.current = false
    } else {
      checkScrollPosition()
    }
  }, [turns, checkScrollPosition])

  useEffect(() => {
    isInitialScroll.current = true
  }, [session?.key])

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

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
    <div className="flex-1 min-w-0 flex flex-col bg-[var(--bg-primary)] relative">
      {/* Session header */}
      <div className="px-4 py-2.5 border-b border-[var(--border)] flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-[var(--text-primary)] flex items-center gap-1.5">
            {session.key}
            <button
              onClick={() => {
                navigator.clipboard.writeText(session.key)
                setKeyCopied(true)
                setTimeout(() => setKeyCopied(false), 1500)
              }}
              className="p-0.5 rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors"
              title="Copy session key"
            >
              {keyCopied ? <Check className="w-3 h-3 text-[var(--success)]" /> : <Copy className="w-3 h-3" />}
            </button>
          </h3>
          <p className="text-[10px] text-[var(--text-secondary)]">
            {SCENE_LABELS[session.scene]}
            {' · '}
            {formatTokenCount(session.token_stats.total_tokens)} tokens
            {' · '}
            {session.token_stats.llm_calls} LLM calls
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          {!isConsole && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">
              Read-only
            </span>
          )}
          <button
            onClick={() => {
              setRefreshing(true)
              onRefresh()
              setTimeout(() => setRefreshing(false), 1000)
            }}
            className="p-1.5 rounded-md text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setShowSearch(true)}
            className="p-1.5 rounded-md text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors"
            title="Search"
          >
            <Search className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-4 space-y-4 relative" ref={scrollContainerRef}>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-[var(--accent)]" />
          </div>
        ) : (
          <>
            {turns.map((turn, i) => (
              <TurnGroupComponent key={i} turn={turn} index={i} tokenStats={turnTokenStats.get(i)} sessionKey={session?.key} />
            ))}
            {thinkingStreaming && (
              <div className="flex justify-start">
                <div
                  className="max-w-[80%] rounded-2xl rounded-bl-md border border-[var(--border)] text-sm overflow-hidden"
                  style={{ background: 'var(--bg-tertiary, var(--bg-secondary))' }}
                >
                  <button
                    onClick={() => setThinkingExpanded(v => !v)}
                    className="flex items-center gap-1.5 w-full px-3 py-1.5 text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
                  >
                    <Brain className="w-3.5 h-3.5 text-[var(--accent)] animate-pulse" />
                    <span className="font-medium">Thinking...</span>
                    {thinkingExpanded ? (
                      <ChevronDown className="w-3 h-3 ml-auto" />
                    ) : (
                      <ChevronRight className="w-3 h-3 ml-auto" />
                    )}
                  </button>
                  {thinkingExpanded && (
                    <div className="px-3 pb-2 border-t border-[var(--border)]">
                      <pre className="whitespace-pre-wrap font-[inherit] text-[12px] text-[var(--text-secondary)] italic leading-relaxed max-h-[200px] overflow-y-auto mt-1.5">
                        {thinkingStreaming}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            )}
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

      {/* Scroll to bottom floating button */}
      {showScrollDown && (
        <div className="absolute bottom-20 right-8 z-10">
          <button
            onClick={scrollToBottom}
            className="p-2 rounded-full bg-[var(--bg-secondary)] border border-[var(--border)] shadow-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors"
            title="Scroll to bottom"
          >
            <ArrowDown className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Input (console only) */}
      {isConsole && <ChatInput onSend={onSend} disabled={sending} />}

      {/* Search modal */}
      {showSearch && (
        <SearchModal turns={turns} onClose={() => setShowSearch(false)} />
      )}
    </div>
  );
}
