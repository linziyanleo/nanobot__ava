import { useEffect, useRef, useState, useCallback } from 'react'
import { api, wsUrl } from '../../api/client'
import { useAuth } from '../../stores/auth'
import type { SceneType, SessionMeta, RawMessage, TurnGroup } from './types'
import { SCENE_ORDER } from './types'
import type { FileTreeNode } from './utils'
import { parseScene, parseJsonl, groupTurns, extractSessionFiles } from './utils'
import { SceneTabs } from './SceneTabs'
import { SessionSidebar } from './SessionSidebar'
import { MessageArea } from './MessageArea'

export default function ChatPage() {
  const [sessions, setSessions] = useState<SessionMeta[]>([])
  const [activeScene, setActiveScene] = useState<SceneType>('console')
  const [activeSession, setActiveSession] = useState('')
  const [currentMeta, setCurrentMeta] = useState<SessionMeta | null>(null)
  const [turns, setTurns] = useState<TurnGroup[]>([])
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [streaming, setStreaming] = useState('')
  const [sending, setSending] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  useAuth()

  const loadSessionList = useCallback(async () => {
    try {
      const tree = await api<FileTreeNode>('/files/tree?root=workspace')
      const sessionFiles = extractSessionFiles(tree)

      const metas: SessionMeta[] = []
      for (const { name, path: fpath } of sessionFiles) {
        try {
          const data = await api<{ content: string; path: string }>(`/files/read?path=${encodeURIComponent(fpath)}`)
          const firstLine = data.content.split('\n')[0]
          if (firstLine) {
            const parsed = JSON.parse(firstLine)
            if (parsed._type === 'metadata') {
              metas.push({
                filename: name,
                filepath: fpath,
                scene: parseScene(name),
                key: parsed.key || name,
                created_at: parsed.created_at || '',
                updated_at: parsed.updated_at || '',
                token_stats: parsed.token_stats || {
                  total_prompt_tokens: 0,
                  total_completion_tokens: 0,
                  total_tokens: 0,
                  llm_calls: 0,
                },
              })
            }
          }
        } catch {
          metas.push({
            filename: name,
            filepath: fpath,
            scene: parseScene(name),
            key: name,
            created_at: '',
            updated_at: '',
            token_stats: { total_prompt_tokens: 0, total_completion_tokens: 0, total_tokens: 0, llm_calls: 0 },
          })
        }
      }

      metas.sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''))
      setSessions(metas)

      if (metas.length > 0 && !activeSession) {
        const firstScene = SCENE_ORDER.find((s) => metas.some((m) => m.scene === s)) || metas[0].scene
        setActiveScene(firstScene)
      }
    } catch (err) {
      console.error('Failed to load sessions:', err)
    }
  }, [activeSession])

  const loadSessionMessages = useCallback(async (filename: string, filepath?: string) => {
    setLoadingMessages(true)
    const readPath = filepath || sessions.find((s) => s.filename === filename)?.filepath || `workspace/sessions/${filename}`
    try {
      const data = await api<{ content: string }>(`/files/read?path=${encodeURIComponent(readPath)}`)
      const { meta, messages } = parseJsonl(data.content, filename)
      if (meta) meta.filepath = readPath
      setCurrentMeta(meta)
      setTurns(groupTurns(messages))
    } catch (err) {
      console.error('Failed to load messages:', err)
      setTurns([])
    } finally {
      setLoadingMessages(false)
    }
  }, [sessions])

  useEffect(() => {
    loadSessionList()
  }, [loadSessionList])

  const handleSessionSelect = (filename: string) => {
    setActiveSession(filename)
    setStreaming('')
    wsRef.current?.close()

    const meta = sessions.find((s) => s.filename === filename)
    loadSessionMessages(filename, meta?.filepath)

    if (meta?.scene === 'console') {
      const sid = filename.replace(/^console_/, '').replace(/\.jsonl$/, '')
      connectWs(sid)
    }
  }

  const handleSceneChange = (scene: SceneType) => {
    setActiveScene(scene)
  }

  const [error, setError] = useState('')

  const handleCreateConsole = async () => {
    setError('')
    try {
      const title = `Chat ${sessions.filter((s) => s.scene === 'console').length + 1}`
      const res = await api<{ session_id: string }>('/chat/sessions', {
        method: 'POST',
        body: JSON.stringify({ title }),
      })

      const sid = res.session_id
      const newFilename = `console_${sid}.jsonl`
      const newFilepath = `workspace/sessions/${newFilename}`

      setActiveScene('console')
      setActiveSession(newFilename)
      setCurrentMeta({
        filename: newFilename,
        filepath: newFilepath,
        scene: 'console',
        key: `console:${sid}`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        token_stats: { total_prompt_tokens: 0, total_completion_tokens: 0, total_tokens: 0, llm_calls: 0 },
      })
      setTurns([])
      connectWs(sid)

      loadSessionList()
    } catch (err: any) {
      const msg = err?.message || String(err)
      if (msg.includes('503') || msg.includes('405')) {
        setError('Chat service unavailable — gateway may be offline. Console chat requires a running gateway.')
      } else {
        setError(msg)
      }
      console.error('Failed to create session:', err)
    }
  }

  const handleDeleteSession = async (filename: string) => {
    const sid = filename.replace(/^console_/, '').replace(/\.jsonl$/, '')
    try {
      await api(`/chat/sessions/${sid}`, { method: 'DELETE' })
      if (activeSession === filename) {
        setActiveSession('')
        setCurrentMeta(null)
        setTurns([])
        wsRef.current?.close()
      }
      loadSessionList()
    } catch (err) {
      console.error('Failed to delete session:', err)
    }
  }

  const connectWs = (sid: string) => {
    wsRef.current?.close()
    const ws = new WebSocket(wsUrl(`/chat/ws/${sid}`))
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'progress') {
        setStreaming((prev) => prev + data.content)
      } else if (data.type === 'complete') {
        setStreaming('')
        setSending(false)
        if (activeSession) {
          loadSessionMessages(activeSession, undefined)
        }
      }
    }
    ws.onerror = () => setSending(false)
    ws.onclose = () => setSending(false)
    wsRef.current = ws
  }

  const handleSend = (message: string) => {
    if (!wsRef.current || sending) return
    setStreaming('')
    setSending(true)

    const userMsg: RawMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    }
    setTurns((prev) => [...prev, {
      userMessage: userMsg,
      assistantSteps: [],
      isComplete: false,
      startTime: userMsg.timestamp,
      toolCalls: [],
    }])

    wsRef.current.send(JSON.stringify({ content: message }))
  }

  const isConsole = activeScene === 'console'
  const filteredSessions = sessions.filter((s) => s.scene === activeScene)

  return (
    <div className="-m-6 h-screen flex flex-col">
      {/* Top scene tabs bar */}
      <SceneTabs
        sessions={sessions}
        activeScene={activeScene}
        onSceneChange={handleSceneChange}
      />

      {/* Error banner */}
      {error && (
        <div className="px-4 py-2 bg-[var(--danger)]/10 text-[var(--danger)] text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="ml-2 hover:underline">Dismiss</button>
        </div>
      )}

      {/* Main content: sidebar + message area */}
      <div className="flex-1 flex min-h-0 min-w-0">
        <SessionSidebar
          sessions={filteredSessions}
          activeSession={activeSession}
          isConsoleScene={isConsole}
          onSessionSelect={handleSessionSelect}
          onCreateConsole={handleCreateConsole}
          onDeleteSession={handleDeleteSession}
        />
        <MessageArea
          session={currentMeta}
          turns={turns}
          loading={loadingMessages}
          isConsole={isConsole && !!activeSession}
          streaming={streaming}
          sending={sending}
          onSend={handleSend}
        />
      </div>
    </div>
  )
}
