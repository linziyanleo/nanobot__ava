import { useState, useMemo, useEffect } from 'react'
import { ChevronDown, ChevronRight, Wrench, Loader2, Image, Eye, Mic } from 'lucide-react'
import { cn } from '../../lib/utils'
import type { ToolCallWithResult } from './types'
import { getContentText, imageUrl, extractImagePaths } from './utils'
import { ImageCarousel } from './ImageCarousel'
import { api } from '../../api/client'

interface MediaRecord {
  id: string
  output_images: string[]
  prompt: string
  status: string
}

interface MediaResponse {
  records: MediaRecord[]
}

interface ToolCallBlockProps {
  tc: ToolCallWithResult
  isLoading: boolean
}

const MEDIA_TOOLS: Record<string, { icon: typeof Image; label: string; color: string }> = {
  image_gen: { icon: Image, label: 'Image Generation', color: 'text-purple-400' },
  vision: { icon: Eye, label: 'Image Analysis', color: 'text-blue-400' },
  analyze_image: { icon: Eye, label: 'Image Analysis', color: 'text-blue-400' },
  transcribe: { icon: Mic, label: 'Voice Transcription', color: 'text-green-400' },
}

export function ToolCallBlock({ tc, isLoading }: ToolCallBlockProps) {
  const [expanded, setExpanded] = useState(false)

  const fnName = tc.call.function.name
  const mediaTool = MEDIA_TOOLS[fnName]
  let args = ''
  let parsedArgs: Record<string, unknown> = {}
  try {
    parsedArgs = JSON.parse(tc.call.function.arguments)
    args = JSON.stringify(parsedArgs, null, 2)
  } catch {
    args = tc.call.function.arguments
  }

  const resultText = tc.result ? getContentText(tc.result.content) : null
  let resultPreview = ''
  if (resultText) {
    resultPreview = resultText.length > 120 ? resultText.slice(0, 120) + '...' : resultText
  }

  const regexImageUrls = useMemo(() => {
    if (fnName === 'image_gen' && resultText) {
      return extractImagePaths(resultText).map((p) => imageUrl(p))
    }
    if ((fnName === 'vision' || fnName === 'analyze_image') && parsedArgs.url) {
      const u = parsedArgs.url as string
      if (u.startsWith('http://') || u.startsWith('https://')) return [u]
    }
    return []
  }, [fnName, resultText, parsedArgs.url])

  const [apiImageUrls, setApiImageUrls] = useState<string[]>([])
  const prompt = (parsedArgs.prompt || '') as string

  useEffect(() => {
    if (fnName !== 'image_gen' || regexImageUrls.length > 0 || !prompt) return
    if (!resultText && !tc.result) return
    let cancelled = false
    const searchTerm = prompt.slice(0, 60)
    api<MediaResponse>(`/media/records?search=${encodeURIComponent(searchTerm)}&size=5`)
      .then((res) => {
        if (cancelled) return
        const match = res.records.find(
          (r) => r.status === 'success' && r.prompt === prompt && r.output_images.length > 0,
        )
        if (match) {
          setApiImageUrls(match.output_images.map((p) => imageUrl(p)))
        }
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [fnName, prompt, regexImageUrls.length, resultText, tc.result])

  const mediaImageUrls = regexImageUrls.length > 0 ? regexImageUrls : apiImageUrls

  if (mediaTool) {
    const ToolIcon = mediaTool.icon
    const displayPrompt = (parsedArgs.prompt || parsedArgs.query || '') as string
    return (
      <div className={cn(
        'my-1 rounded-lg border text-xs',
        'border-[var(--border)] bg-[var(--bg-primary)]/50',
      )}>
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1.5 w-full px-3 py-2 text-left hover:bg-[var(--bg-tertiary)]/30 rounded-lg transition-colors"
        >
          {isLoading ? (
            <Loader2 className={cn('w-3.5 h-3.5 shrink-0 animate-spin', mediaTool.color)} />
          ) : expanded ? (
            <ChevronDown className="w-3 h-3 shrink-0 text-[var(--text-secondary)]" />
          ) : (
            <ChevronRight className="w-3 h-3 shrink-0 text-[var(--text-secondary)]" />
          )}
          <ToolIcon className={cn('w-3.5 h-3.5 shrink-0', mediaTool.color)} />
          <span className={cn('font-medium', mediaTool.color)}>{mediaTool.label}</span>
          {displayPrompt && !expanded && (
            <span className="text-[var(--text-secondary)] truncate ml-1">— {displayPrompt.slice(0, 60)}{displayPrompt.length > 60 ? '...' : ''}</span>
          )}
        </button>

        {expanded && (
          <div className="px-3 pb-2 space-y-2 border-t border-[var(--border)]">
            {displayPrompt && (
              <div className="pt-1.5">
                <div className="text-[var(--text-secondary)] mb-0.5 font-medium">Prompt</div>
                <div className="text-[var(--text-primary)] text-[11px]">{displayPrompt}</div>
              </div>
            )}
            {args && args !== '{}' && !displayPrompt && (
              <div className="pt-1.5">
                <div className="text-[var(--text-secondary)] mb-0.5 font-medium">Arguments</div>
                <pre className="bg-[var(--bg-tertiary)] rounded p-2 overflow-x-auto whitespace-pre-wrap text-[var(--text-primary)] max-h-48 overflow-y-auto">
                  {args}
                </pre>
              </div>
            )}
            {mediaImageUrls.length > 0 && (
              <div className="pt-1">
                <ImageCarousel urls={mediaImageUrls} alt={displayPrompt || fnName} />
              </div>
            )}
            {resultText !== null && (
              <div>
                <div className="text-[var(--text-secondary)] mb-0.5 font-medium">Result</div>
                <pre className="bg-[var(--bg-tertiary)] rounded p-2 overflow-x-auto whitespace-pre-wrap text-[var(--text-primary)] max-h-64 overflow-y-auto">
                  {resultText}
                </pre>
              </div>
            )}
            {isLoading && !resultText && (
              <div className="flex items-center gap-1.5 text-[var(--warning)] py-1">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>Processing...</span>
              </div>
            )}
          </div>
        )}
      </div>
    )
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
