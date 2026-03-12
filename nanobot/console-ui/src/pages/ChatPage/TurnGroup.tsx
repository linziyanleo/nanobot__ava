import { useState, useRef, useEffect } from 'react'
import { Loader2, Clock, Info } from 'lucide-react'
import type { TurnGroup as TurnGroupType, TurnTokenStats } from './types'
import { MessageBubble } from './MessageBubble'
import { ToolCallBlock } from './ToolCallBlock'
import { formatTimestamp, calcDuration, getContentText, formatTokenCount } from './utils'

interface TurnGroupProps {
  turn: TurnGroupType
  tokenStats?: TurnTokenStats
}

function TokenInfoPopover({ stats }: { stats: TurnTokenStats }) {
  return (
    <div className="absolute left-0 bottom-full mb-1 z-50 w-52 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] shadow-lg p-2.5 text-[10px]">
      <div className="space-y-1">
        <div className="flex justify-between">
          <span className="text-[var(--text-secondary)]">Prompt</span>
          <span className="font-mono text-[var(--text-primary)]">{formatTokenCount(stats.prompt_tokens)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[var(--text-secondary)]">Completion</span>
          <span className="font-mono text-[var(--text-primary)]">{formatTokenCount(stats.completion_tokens)}</span>
        </div>
        <div className="flex justify-between border-t border-[var(--border)] pt-1">
          <span className="text-[var(--text-secondary)] font-medium">Total</span>
          <span className="font-mono font-medium text-[var(--accent)]">{formatTokenCount(stats.total_tokens)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[var(--text-secondary)]">LLM Calls</span>
          <span className="font-mono text-[var(--text-primary)]">{stats.llm_calls}</span>
        </div>
        {stats.models && (
          <div className="border-t border-[var(--border)] pt-1 truncate">
            <span className="text-[var(--text-secondary)]">Model: </span>
            <span className="text-[var(--text-primary)]">{stats.models}</span>
          </div>
        )}
      </div>
    </div>
  )
}

export function TurnGroupComponent({ turn, tokenStats }: TurnGroupProps) {
  const duration = calcDuration(turn.startTime, turn.endTime)
  const hasToolCalls = turn.toolCalls.length > 0
  const [showTokenInfo, setShowTokenInfo] = useState(false)
  const popoverRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!showTokenInfo) return
    const handler = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setShowTokenInfo(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showTokenInfo])

  const finalAssistant = turn.assistantSteps.filter(
    (s) => s.role === 'assistant' && !s.tool_calls && s.content !== null,
  )

  const hasFinalText = finalAssistant.some((s) => getContentText(s.content))

  const intermediateAssistants = turn.assistantSteps.filter(
    (s) => s.role === 'assistant' && s.tool_calls && getContentText(s.content),
  )

  return (
    <div className="space-y-2">
      {/* User message */}
      <MessageBubble message={turn.userMessage} isUser />

      {/* Intermediate assistant messages with content before tool calls */}
      {intermediateAssistants.map((msg, i) => (
        <MessageBubble key={`intermediate-${i}`} message={msg} isUser={false} />
      ))}

      {/* Tool calls */}
      {hasToolCalls && (
        <div className="ml-2 pl-3 border-l-2 border-[var(--border)] space-y-1">
          <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-secondary)] py-0.5">
            <Clock className="w-3 h-3" />
            <span>{formatTimestamp(turn.startTime)}</span>
            {duration && <span className="text-[var(--accent)]">({duration})</span>}
            <span>{turn.toolCalls.length} tool call{turn.toolCalls.length > 1 ? 's' : ''}</span>
            {tokenStats && !hasFinalText && (
              <div className="relative" ref={popoverRef}>
                <button
                  onClick={() => setShowTokenInfo(!showTokenInfo)}
                  className="flex items-center gap-0.5 hover:text-[var(--accent)] transition-colors"
                  title="Token usage"
                >
                  <Info className="w-3 h-3" />
                  <span>{formatTokenCount(tokenStats.total_tokens)}</span>
                </button>
                {showTokenInfo && <TokenInfoPopover stats={tokenStats} />}
              </div>
            )}
          </div>
          {turn.toolCalls.map((tc, i) => (
            <ToolCallBlock
              key={tc.call.id || i}
              tc={tc}
              isLoading={!turn.isComplete && !tc.result}
            />
          ))}
        </div>
      )}

      {/* Final assistant response — pass token stats to the last bubble */}
      {finalAssistant.map((msg, i) => (
        <MessageBubble
          key={`final-${i}`}
          message={msg}
          isUser={false}
          tokenStats={i === finalAssistant.length - 1 ? tokenStats : undefined}
        />
      ))}

      {/* Loading indicator for incomplete turns */}
      {!turn.isComplete && (
        <div className="flex justify-start">
          <div className="flex items-center gap-2 px-4 py-2.5 rounded-2xl rounded-bl-md bg-[var(--bg-secondary)] border border-[var(--border)] text-sm text-[var(--text-secondary)]">
            <Loader2 className="w-4 h-4 animate-spin text-[var(--accent)]" />
            <span>Processing...</span>
          </div>
        </div>
      )}
    </div>
  )
}
