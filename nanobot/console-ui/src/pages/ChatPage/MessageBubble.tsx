import { Copy, Check, Brain, ChevronDown, ChevronRight, Info } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { cn } from '../../lib/utils';
import type { RawMessage, TurnTokenStats } from './types';
import { getContentText, formatTimestamp, formatTokenCount } from './utils';

interface MessageBubbleProps {
  message: RawMessage;
  isUser: boolean;
  tokenStats?: TurnTokenStats;
}

function TokenInfoPopover({ stats }: { stats: TurnTokenStats }) {
  console.log('TokenInfoPopover', stats);
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
  );
}

export function MessageBubble({ message, isUser, tokenStats }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const [reasoningExpanded, setReasoningExpanded] = useState(false);
  const [showTokenInfo, setShowTokenInfo] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const text = getContentText(message.content);
  const reasoning = message.reasoning_content;
  console.log('MessageBubble', message, tokenStats);
  useEffect(() => {
    if (!showTokenInfo) return;
    const handler = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setShowTokenInfo(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showTokenInfo]);

  if (!text && !reasoning) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className={cn('flex group', isUser ? 'justify-end' : 'justify-start')}>
      <div className="relative max-w-[80%]">
        {/* Reasoning content (collapsible, shown above the main bubble for assistant) */}
        {!isUser && reasoning && (
          <div
            className="mb-1 rounded-xl border border-[var(--border)] overflow-hidden"
            style={{ background: 'var(--bg-tertiary, var(--bg-secondary))' }}
          >
            <button
              onClick={() => setReasoningExpanded(v => !v)}
              className="flex items-center gap-1.5 w-full px-3 py-1.5 text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              <Brain className="w-3.5 h-3.5 text-[var(--accent)]" />
              <span className="font-medium">Thinking</span>
              {reasoningExpanded ? (
                <ChevronDown className="w-3 h-3 ml-auto" />
              ) : (
                <ChevronRight className="w-3 h-3 ml-auto" />
              )}
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
            <div
              className={cn(
                'flex items-center gap-2 mt-0.5 text-[10px] text-[var(--text-secondary)]',
                isUser ? 'justify-end' : 'justify-start',
              )}
            >
              {message.timestamp && <span>{formatTimestamp(message.timestamp)}</span>}
              <button
                onClick={handleCopy}
                className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 hover:text-[var(--text-primary)]"
                title="Copy"
              >
                {copied ? <Check className="w-3 h-3 text-[var(--success)]" /> : <Copy className="w-3 h-3" />}
              </button>
              {tokenStats && !isUser && (
                <div className="relative" ref={popoverRef}>
                  <button
                    onClick={() => setShowTokenInfo(!showTokenInfo)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 hover:text-[var(--accent)] flex items-center gap-0.5"
                    title="Token usage"
                  >
                    <Info className="w-3 h-3" />
                    <span>{formatTokenCount(tokenStats.total_tokens)}</span>
                  </button>
                  {showTokenInfo && <TokenInfoPopover stats={tokenStats} />}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
