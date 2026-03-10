import { Copy, Check, Brain, ChevronDown, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { cn } from '../../lib/utils'
import type { RawMessage } from './types'
import { getContentText, formatTimestamp } from './utils'

interface MessageBubbleProps {
  message: RawMessage
  isUser: boolean
}

export function MessageBubble({ message, isUser }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false)
  const [reasoningExpanded, setReasoningExpanded] = useState(false)
  const text = getContentText(message.content)
  const reasoning = message.reasoning_content

  if (!text && !reasoning) return null

  const handleCopy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className={cn('flex group', isUser ? 'justify-end' : 'justify-start')}>
      <div className="relative max-w-[80%]">
        {/* Reasoning content (collapsible, shown above the main bubble for assistant) */}
        {!isUser && reasoning && (
          <div className="mb-1 rounded-xl border border-[var(--border)] overflow-hidden"
            style={{ background: 'var(--bg-tertiary, var(--bg-secondary))' }}>
            <button
              onClick={() => setReasoningExpanded((v) => !v)}
              className="flex items-center gap-1.5 w-full px-3 py-1.5 text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              <Brain className="w-3.5 h-3.5 text-[var(--accent)]" />
              <span className="font-medium">Thinking</span>
              {reasoningExpanded
                ? <ChevronDown className="w-3 h-3 ml-auto" />
                : <ChevronRight className="w-3 h-3 ml-auto" />}
            </button>
            {reasoningExpanded && (
              <div className="px-3 pb-2 border-t border-[var(--border)]">
                <pre className="whitespace-pre-wrap font-[inherit] text-[12px] text-[var(--text-secondary)] italic leading-relaxed max-h-[300px] overflow-y-auto mt-1.5 break-words">
                  {reasoning}
                </pre>
              </div>
            )}
          </div>
        )}

        {text && (
          <>
            <div
              className={cn(
                'px-4 py-2.5 rounded-2xl text-sm leading-relaxed',
                isUser
                  ? 'bg-[var(--accent)] text-white rounded-br-md'
                  : 'bg-[var(--bg-secondary)] text-[var(--text-primary)] rounded-bl-md border border-[var(--border)]',
              )}
            >
              <pre className="whitespace-pre-wrap font-[inherit] break-words">{text}</pre>
            </div>
            <div className={cn(
              'flex items-center gap-2 mt-0.5 text-[10px] text-[var(--text-secondary)]',
              isUser ? 'justify-end' : 'justify-start',
            )}>
              {message.timestamp && <span>{formatTimestamp(message.timestamp)}</span>}
              <button
                onClick={handleCopy}
                className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 hover:text-[var(--text-primary)]"
                title="Copy"
              >
                {copied ? <Check className="w-3 h-3 text-[var(--success)]" /> : <Copy className="w-3 h-3" />}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
