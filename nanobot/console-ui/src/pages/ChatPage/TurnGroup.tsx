import { Loader2, Clock } from 'lucide-react'
import type { TurnGroup as TurnGroupType } from './types'
import { MessageBubble } from './MessageBubble'
import { ToolCallBlock } from './ToolCallBlock'
import { formatTimestamp, calcDuration, getContentText } from './utils'

interface TurnGroupProps {
  turn: TurnGroupType
}

export function TurnGroupComponent({ turn }: TurnGroupProps) {
  const duration = calcDuration(turn.startTime, turn.endTime)
  const hasToolCalls = turn.toolCalls.length > 0

  const finalAssistant = turn.assistantSteps.filter(
    (s) => s.role === 'assistant' && !s.tool_calls && s.content !== null,
  )

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

      {/* Final assistant response */}
      {finalAssistant.map((msg, i) => (
        <MessageBubble key={`final-${i}`} message={msg} isUser={false} />
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
