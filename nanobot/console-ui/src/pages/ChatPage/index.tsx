import { useEffect, useRef, useState, useCallback } from 'react'
import { api, wsUrl } from '../../api/client'
import { useAuth } from '../../stores/auth'
import type { SceneType, SessionMeta, RawMessage, TurnGroup } from './types'
import { SCENE_ORDER } from './types'
import { groupTurns } from './utils'
import { SceneTabs } from './SceneTabs'
import { SessionSidebar } from './SessionSidebar'
import { MessageArea } from './MessageArea'

const SESSION_LIST_POLL_MS = 30_000
const MESSAGE_POLL_MS = 10_000

export default function ChatPage() {
  const [sessions, setSessions] = useState<SessionMeta[]>([])
  const [activeScene, setActiveScene] = useState<SceneType>('console')
  const [activeSession, setActiveSession] = useState('')
  const [currentMeta, setCurrentMeta] = useState<SessionMeta | null>(null)
  const [turns, setTurns] = useState<TurnGroup[]>([])
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [streaming, setStreaming] = useState('')
  const [thinkingStreaming, setThinkingStreaming] = useState('')
  const [sending, setSending] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const initializedRef = useRef(false)
  useAuth()

  const loadSessionList = useCallback(async () => {
    try {
      const data = await api<SessionMeta[]>('/chat/sessions')
      const metas: SessionMeta[] = data.map((s) => ({
        ...s,
        token_stats: s.token_stats || {
          total_prompt_tokens: 0,
          total_completion_tokens: 0,
          total_tokens: 0,
          llm_calls: 0,
        },
        message_count: s.message_count || 0,
      }))

      setSessions(metas)

      if (!initializedRef.current && metas.length > 0) {
        initializedRef.current = true
        const firstScene = SCENE_ORDER.find((s) => metas.some((m) => m.scene === s)) || metas[0].scene
        setActiveScene(firstScene)
        const firstSessionInScene = metas.find((m) => m.scene === firstScene)
        if (firstSessionInScene) {
          setActiveSession(firstSessionInScene.key)
          setCurrentMeta(firstSessionInScene)
          loadSessionMessages(firstSessionInScene.key)
          if (firstScene === 'console') {
            const sid = firstSessionInScene.key.replace(/^console:/, '')
            connectWs(sid)
          }
        }
      }
    } catch (err) {
      console.error('Failed to load sessions:', err)
    }
  }, [])

  const loadSessionMessages = useCallback(async (sessionKey: string, silent = false) => {
    if (!silent) setLoadingMessages(true)
    try {
      const messages = await api<RawMessage[]>(`/chat/messages?session_key=${encodeURIComponent(sessionKey)}`)
      const meta = sessions.find((s) => s.key === sessionKey) || null
      setCurrentMeta(meta)
      setTurns(groupTurns(messages))
    } catch (err) {
      console.error('Failed to load messages:', err)
      if (!silent) setTurns([])
    } finally {
      if (!silent) setLoadingMessages(false)
    }
  }, [sessions])

  useEffect(() => {
    loadSessionList()
  }, [loadSessionList])

  // Session list polling (30s)
  useEffect(() => {
    const timer = setInterval(loadSessionList, SESSION_LIST_POLL_MS)
    return () => clearInterval(timer)
  }, [loadSessionList])

  // Current session message polling (10s, non-console only)
  useEffect(() => {
    if (!activeSession || activeScene === 'console' || sending) return
    const timer = setInterval(() => {
      loadSessionMessages(activeSession, true)
    }, MESSAGE_POLL_MS)
    return () => clearInterval(timer)
  }, [activeSession, activeScene, sending, loadSessionMessages])

  const handleSessionSelect = (key: string) => {
    setActiveSession(key)
    setStreaming('')
    setThinkingStreaming('')
    wsRef.current?.close()

    loadSessionMessages(key)

    const meta = sessions.find((s) => s.key === key)
    if (meta?.scene === 'console') {
      const sid = key.replace(/^console:/, '')
      connectWs(sid)
    }
  }

  const handleSceneChange = (scene: SceneType) => {
    setActiveScene(scene)
    wsRef.current?.close()
    setStreaming('')
    setThinkingStreaming('')

    const sceneSessions = sessions.filter((s) => s.scene === scene)
    if (sceneSessions.length > 0) {
      const first = sceneSessions[0]
      setActiveSession(first.key)
      loadSessionMessages(first.key)
      if (scene === 'console') {
        const sid = first.key.replace(/^console:/, '')
        connectWs(sid)
      }
    } else {
      setActiveSession('')
      setCurrentMeta(null)
      setTurns([])
    }
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
      const newKey = `console:${sid}`

      setActiveScene('console')
      setActiveSession(newKey)
      setCurrentMeta({
        key: newKey,
        scene: 'console',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        token_stats: { total_prompt_tokens: 0, total_completion_tokens: 0, total_tokens: 0, llm_calls: 0 },
        message_count: 0,
      })
      setTurns([])
      connectWs(sid)

      loadSessionList()
    } catch (err: any) {
      const msg = err?.message || String(err)
      setError(msg)
      console.error('Failed to create session:', err)
    }
  }

  const handleDeleteSession = async (key: string) => {
    const meta = sessions.find((s) => s.key === key)
    try {
      if (meta?.scene === 'console') {
        const sid = key.replace(/^console:/, '')
        await api(`/chat/sessions/${sid}`, { method: 'DELETE' })
      } else {
        // For non-console sessions, delete via DB (using key as session_id path)
        // The backend delete_session expects the session_id part after "console:"
        // For non-console, we need a different approach — use session key
        const safe = key.replace(/:/g, '_')
        await api('/files/delete', {
          method: 'DELETE',
          body: JSON.stringify({ path: `workspace/sessions/${safe}.jsonl` }),
        })
      }
      if (activeSession === key) {
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

  const handleRenameSession = async (key: string, newName: string) => {
    // Rename is only meaningful for console sessions with DB
    // For now, keep as no-op for non-console sessions
    console.log('Rename not yet supported for key-based sessions:', key, newName)
    // TODO: Add rename API endpoint
  }

  const handleRefresh = useCallback(() => {
    loadSessionList()
    if (activeSession) {
      loadSessionMessages(activeSession)
    }
  }, [activeSession, loadSessionList, loadSessionMessages])

  const activeSessionRef = useRef(activeSession)
  activeSessionRef.current = activeSession

  const connectWs = useCallback((sid: string) => {
    wsRef.current?.close()
    const sessionKey = `console:${sid}`
    const ws = new WebSocket(wsUrl(`/chat/ws/${sid}`))
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'thinking') {
        setThinkingStreaming((prev) => prev + data.content)
      } else if (data.type === 'progress') {
        setStreaming((prev) => prev + data.content)
      } else if (data.type === 'complete') {
        setStreaming('')
        setThinkingStreaming('')
        setSending(false)
        loadSessionMessages(sessionKey)
      }
    }
    ws.onerror = () => setSending(false)
    ws.onclose = () => setSending(false)
    wsRef.current = ws
  }, [loadSessionMessages])

  const handleSend = (message: string) => {
    if (!wsRef.current || sending) return
    setStreaming('')
    setThinkingStreaming('')
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
    <div className="-m-6 h-[calc(100vh)] flex flex-col overflow-hidden">
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
          onRenameSession={handleRenameSession}
        />
        <MessageArea
          session={currentMeta}
          turns={turns}
          loading={loadingMessages}
          isConsole={isConsole && !!activeSession}
          streaming={streaming}
          thinkingStreaming={thinkingStreaming}
          sending={sending}
          onSend={handleSend}
          onRefresh={handleRefresh}
        />
      </div>
    </div>
  )
}
