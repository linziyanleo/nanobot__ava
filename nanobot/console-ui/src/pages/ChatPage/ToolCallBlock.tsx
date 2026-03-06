import { useState } from 'react'
import { ChevronDown, ChevronRight, Wrench, Loader2 } from 'lucide-react'
import { cn } from '../../lib/utils'
import type { ToolCallWithResult } from './types'
import { getContentText } from './utils'

interface ToolCallBlockProps {
  tc: ToolCallWithResult
  isLoading: boolean
}

export function ToolCallBlock({ tc, isLoading }: ToolCallBlockProps) {
  const [expanded, setExpanded] = useState(false)

  const fnName = tc.call.function.name
  let args = ''
  try {
    const parsed = JSON.parse(tc.call.function.arguments)
    args = JSON.stringify(parsed, null, 2)
  } catch {
    args = tc.call.function.arguments
  }

  const resultText = tc.result ? getContentText(tc.result.content) : null
  let resultPreview = ''
  if (resultText) {
    resultPreview = resultText.length > 120 ? resultText.slice(0, 120) + '...' : resultText
  }

  return (
    <div className="my-1 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)]/50 text-xs">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 w-full px-3 py-1.5 text-left hover:bg-[var(--bg-tertiary)]/30 rounded-lg transition-colors"
      >
        {isLoading ? (
          <Loader2 className="w-3 h-3 shrink-0 text-[var(--warning)] animate-spin" />
        ) : expanded ? (
          <ChevronDown className="w-3 h-3 shrink-0 text-[var(--text-secondary)]" />
        ) : (
          <ChevronRight className="w-3 h-3 shrink-0 text-[var(--text-secondary)]" />
        )}
        <Wrench className="w-3 h-3 shrink-0 text-[var(--accent)]" />
        <span className="font-mono text-[var(--accent)]">{fnName}</span>
        {!expanded && resultPreview && (
          <span className="text-[var(--text-secondary)] truncate ml-2">{resultPreview}</span>
        )}
      </button>

      {expanded && (
        <div className="px-3 pb-2 space-y-2">
          <div>
            <div className="text-[var(--text-secondary)] mb-0.5 font-medium">Arguments</div>
            <pre className="bg-[var(--bg-tertiary)] rounded p-2 overflow-x-auto whitespace-pre-wrap text-[var(--text-primary)] max-h-48 overflow-y-auto">
              {args}
            </pre>
          </div>
          {resultText !== null && (
            <div>
              <div className="text-[var(--text-secondary)] mb-0.5 font-medium">Result</div>
              <pre className={cn(
                'rounded p-2 overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto',
                'bg-[var(--bg-tertiary)] text-[var(--text-primary)]',
              )}>
                {resultText}
              </pre>
            </div>
          )}
          {isLoading && !resultText && (
            <div className="flex items-center gap-1.5 text-[var(--warning)] py-1">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Waiting for result...</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
