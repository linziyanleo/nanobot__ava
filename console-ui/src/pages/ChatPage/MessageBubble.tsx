import { Copy, Check, Brain, ChevronDown, ChevronRight, Info, Eye, Mic } from 'lucide-react';
import React, { useState, useRef, useEffect, useMemo, Suspense } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { cn } from '../../lib/utils';
import type { RawMessage, TurnTokenStats } from './types';
import { getContentText, formatTimestamp, formatTokenCount } from './utils';
import { TokenInfoPopover } from './TokenInfoPopover';

const SyntaxHighlighter = React.lazy(() =>
  import('react-syntax-highlighter').then(m => ({ default: m.Prism }))
);

interface MediaBlock {
  type: 'vision' | 'voice'
  content: string
}

function parseMediaBlocks(text: string): { mainText: string; blocks: MediaBlock[] } {
  const blocks: MediaBlock[] = []
  let mainText = text

  const patterns: { regex: RegExp; type: 'vision' | 'voice' }[] = [
    { regex: /\[图片识别:\s*([\s\S]*?)\]/g, type: 'vision' },
    { regex: /\[语音转录:\s*([\s\S]*?)\]/g, type: 'voice' },
    { regex: /\[transcription:\s*([\s\S]*?)\]/g, type: 'voice' },
  ]

  for (const { regex, type } of patterns) {
    let match
    while ((match = regex.exec(text)) !== null) {
      blocks.push({ type, content: match[1].trim() })
    }
    mainText = mainText.replace(regex, '').trim()
  }

  return { mainText, blocks }
}

function MediaBlockIndicator({ block }: { block: MediaBlock }) {
  const [expanded, setExpanded] = useState(false)
  const Icon = block.type === 'vision' ? Eye : Mic
  const label = block.type === 'vision' ? 'Image Recognition' : 'Voice Transcription'

  return (
    <div className="mt-1.5 rounded-lg border border-white/20 overflow-hidden">
      <button
        onClick={() => setExpanded(v => !v)}
        className="flex items-center gap-1.5 w-full px-2.5 py-1 text-[11px] text-white/80 hover:text-white transition-colors"
      >
        <Icon className="w-3 h-3" />
        <span className="font-medium">{label}</span>
        {expanded ? <ChevronDown className="w-3 h-3 ml-auto" /> : <ChevronRight className="w-3 h-3 ml-auto" />}
      </button>
      {expanded && (
        <div className="px-2.5 pb-1.5 border-t border-white/10">
          <pre className="whitespace-pre-wrap font-[inherit] text-[11px] text-white/70 leading-relaxed mt-1 break-words max-h-[200px] overflow-y-auto">
            {block.content}
          </pre>
        </div>
      )}
    </div>
  )
}

const MarkdownRenderer = React.memo(function MarkdownRenderer({ content }: { content: string }) {
  const components = useMemo(() => ({
    code({ className, children, ...props }: { className?: string; children?: React.ReactNode; [key: string]: unknown }) {
      const match = /language-(\w+)/.exec(className || '');
      const isInline = !match && !String(children).includes('\n');
      const codeString = String(children).replace(/\n$/, '');
      return isInline ? (
        <code
          className="px-1 py-0.5 rounded text-[0.85em] font-mono bg-black/20 text-[var(--accent)]"
          {...props}
        >
          {children}
        </code>
      ) : (
        <Suspense fallback={<pre className="p-3 rounded-lg bg-[#282c34] text-sm overflow-x-auto my-2"><code>{codeString}</code></pre>}>
          <SyntaxHighlighter
            style={oneDark}
            language={match ? match[1] : 'text'}
            PreTag="div"
            customStyle={{
              margin: '0.5em 0',
              borderRadius: '0.5rem',
              fontSize: '0.8rem',
            }}
          >
            {codeString}
          </SyntaxHighlighter>
        </Suspense>
      );
    },
    a({ children, href }: { children?: React.ReactNode; href?: string }) {
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[var(--accent)] underline hover:opacity-80"
        >
          {children}
        </a>
      );
    },
    table({ children }: { children?: React.ReactNode }) {
      return (
        <div className="overflow-x-auto my-2">
          <table className="min-w-full border-collapse text-sm">
            {children}
          </table>
        </div>
      );
    },
    th({ children }: { children?: React.ReactNode }) {
      return (
        <th className="border border-[var(--border)] px-3 py-1.5 bg-[var(--bg-tertiary,var(--bg-secondary))] font-semibold text-left">
          {children}
        </th>
      );
    },
    td({ children }: { children?: React.ReactNode }) {
      return (
        <td className="border border-[var(--border)] px-3 py-1.5">
          {children}
        </td>
      );
    },
  }), [])

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components as never}>
      {content}
    </ReactMarkdown>
  )
})

interface MessageBubbleProps {
  message: RawMessage;
  isUser: boolean;
  tokenStats?: TurnTokenStats;
  sessionKey?: string;
}

export const MessageBubble = React.memo(function MessageBubble({ message, isUser, tokenStats, sessionKey }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const [reasoningExpanded, setReasoningExpanded] = useState(false);
  const [showTokenInfo, setShowTokenInfo] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const text = getContentText(message.content);
  const reasoning = message.reasoning_content;
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

  const { mainText, blocks: mediaBlocks } = isUser ? parseMediaBlocks(text) : { mainText: text, blocks: [] }
  const displayText = isUser ? mainText : text

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

        {(displayText || mediaBlocks.length > 0) && (
          <>
            <div
              className={cn(
                'px-4 py-2.5 rounded-2xl text-sm leading-relaxed',
                isUser
                  ? 'bg-[var(--accent)] text-white rounded-br-md'
                  : 'bg-[var(--bg-secondary)] text-[var(--text-primary)] rounded-bl-md border border-[var(--border)]',
              )}
            >
              {displayText && (
                isUser ? (
                  <pre className="whitespace-pre-wrap font-[inherit] break-words">{displayText}</pre>
                ) : (
                  <div className="markdown-body">
                    <MarkdownRenderer content={displayText} />
                  </div>
                )
              )}
              {mediaBlocks.map((block, i) => (
                <MediaBlockIndicator key={i} block={block} />
              ))}
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
                  {showTokenInfo && <TokenInfoPopover stats={tokenStats} sessionKey={sessionKey} turnSeq={tokenStats.turn_seq ?? undefined} />}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}, (prev, next) => {
  return prev.message.content === next.message.content &&
         prev.tokenStats === next.tokenStats
})
