import { useEffect, useRef, useState, useCallback } from 'react'
import { api, wsUrl } from '../../api/client'
import { useAuth } from '../../stores/auth'
import { useResponsiveMode } from '../../hooks/useResponsiveMode'
import type { SceneType, SessionMeta, RawMessage, TurnGroup } from './types'
import { SCENE_ORDER } from './types'
import { getNextTurnSeq, groupTurns } from './utils'
import { SceneTabs } from './SceneTabs'
import { SessionSidebar } from './SessionSidebar'
import { MessageArea } from './MessageArea'

const SESSION_LIST_POLL_MS = 30_000

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
  const [processing, setProcessing] = useState(false)
  const [mobileSessionOpen, setMobileSessionOpen] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const wsReconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wsSessionId = useRef<string>('')
  const observeWsRef = useRef<WebSocket | null>(null)
  const observeReconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const observeSessionKey = useRef<string>('')
  const initializedRef = useRef(false)
  const { isMobile } = useResponsiveMode()
  useAuth()

  const loadSessionMessagesWithMeta = useCallback(async (sessionKey: string, meta: SessionMeta | null, silent = false) => {
    if (!silent) setLoadingMessages(true)
    try {
      const messages = await api<RawMessage[]>(`/chat/messages?session_key=${encodeURIComponent(sessionKey)}`)
      setCurrentMeta(meta)
      setTurns(groupTurns(messages))
    } catch (err) {
      console.error('Failed to load messages:', err)
      if (!silent) setTurns([])
    } finally {
      if (!silent) setLoadingMessages(false)
    }
  }, [])

  const loadSessionMessages = useCallback(async (sessionKey: string, silent = false) => {
    const meta = sessions.find((s) => s.key === sessionKey) || null
    return loadSessionMessagesWithMeta(sessionKey, meta, silent)
  }, [sessions, loadSessionMessagesWithMeta])

  const connectWs = useCallback((sid: string, isReconnect = false) => {
    if (wsReconnectTimer.current) {
      clearTimeout(wsReconnectTimer.current)
      wsReconnectTimer.current = null
    }
    wsRef.current?.close()
    wsSessionId.current = sid
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
        void (async () => {
          const metas = await loadSessionListRef.current()
          const meta = metas.find((m) => m.key === sessionKey) || null
          await loadSessionMessagesWithMetaRef.current(sessionKey, meta)
        })()
      } else if (data.type === 'async_result') {
        void (async () => {
          const metas = await loadSessionListRef.current()
          const meta = metas.find((m) => m.key === sessionKey) || null
          await loadSessionMessagesWithMetaRef.current(sessionKey, meta)
        })()
      }
    }
    ws.onerror = () => setSending(false)
    ws.onclose = () => {
      setSending(false)
      // Reload messages on disconnect — the LLM may have finished while ws was down.
      loadSessionMessagesRef.current(sessionKey, true)
      // Auto-reconnect if this is still the active session
      if (wsSessionId.current === sid) {
        wsReconnectTimer.current = setTimeout(() => connectWs(sid, true), 2000)
      }
    }
    wsRef.current = ws
    // If reconnecting after a drop, reload messages to catch anything missed.
    if (isReconnect) {
      loadSessionMessagesRef.current(sessionKey, true)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const disconnectObserveWs = useCallback(() => {
    if (observeReconnectTimer.current) {
      clearTimeout(observeReconnectTimer.current)
      observeReconnectTimer.current = null
    }
    observeWsRef.current?.close()
    observeWsRef.current = null
    observeSessionKey.current = ''
    setProcessing(false)
  }, [])

  const connectObserveWs = useCallback((sessionKey: string) => {
    disconnectObserveWs()
    observeSessionKey.current = sessionKey
    const ws = new WebSocket(wsUrl(`/chat/ws/observe/${encodeURIComponent(sessionKey)}`))

    ws.onopen = () => {
      loadSessionMessagesRef.current(sessionKey, true)
    }

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'message_arrived') {
        const pendingMsg: RawMessage = {
          role: 'user',
          content: data.content,
          timestamp: data.timestamp,
        }
        setTurns((prev) => [...prev, {
          turnSeq: getNextTurnSeq(prev),
          userMessage: pendingMsg,
          assistantSteps: [],
          isComplete: false,
          startTime: data.timestamp,
          toolCalls: [],
        }])
        setProcessing(true)
      } else if (data.type === 'processing_started') {
        setProcessing(true)
      } else if (data.type === 'turn_completed') {
        setProcessing(false)
        void (async () => {
          const metas = await loadSessionListRef.current()
          const meta = metas.find((m) => m.key === sessionKey) || null
          await loadSessionMessagesWithMetaRef.current(sessionKey, meta, true)
        })()
      }
    }

    ws.onclose = () => {
      if (observeSessionKey.current === sessionKey) {
        observeReconnectTimer.current = setTimeout(() => connectObserveWs(sessionKey), 2000)
      }
    }

    observeWsRef.current = ws
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disconnectObserveWs])

  const loadSessionList = useCallback(async () => {
    try {
      const data = await api<SessionMeta[]>('/chat/sessions')
      const metas: SessionMeta[] = data.map((s) => ({
        ...s,
        conversation_id: s.conversation_id || '',
        token_stats: s.token_stats || {
          total_prompt_tokens: 0,
          total_completion_tokens: 0,
          total_tokens: 0,
          llm_calls: 0,
        },
        message_count: s.message_count || 0,
      }))

      setSessions(metas)
      if (activeSession) {
        const activeMeta = metas.find((m) => m.key === activeSession) || null
        if (activeMeta) {
          setCurrentMeta(activeMeta)
        }
      }

      if (!initializedRef.current && metas.length > 0) {
        initializedRef.current = true
        const firstScene = SCENE_ORDER.find((s) => metas.some((m) => m.scene === s)) || metas[0].scene
        setActiveScene(firstScene)
        const firstSessionInScene = metas.find((m) => m.scene === firstScene)
        if (firstSessionInScene) {
          setActiveSession(firstSessionInScene.key)
          loadSessionMessagesWithMeta(firstSessionInScene.key, firstSessionInScene)
          if (firstScene === 'console') {
            const sid = firstSessionInScene.key.replace(/^console:/, '')
            connectWs(sid)
          }
        }
      }
      return metas
    } catch (err) {
      console.error('Failed to load sessions:', err)
      return []
    }
  }, [activeSession, loadSessionMessagesWithMeta, connectWs])

  useEffect(() => {
    loadSessionList()
  }, [loadSessionList])

  // Session list polling (30s)
  useEffect(() => {
    const timer = setInterval(loadSessionList, SESSION_LIST_POLL_MS)
    return () => clearInterval(timer)
  }, [loadSessionList])

  // Observe WS for non-console sessions (replaces 10s polling)
  useEffect(() => {
    if (!activeSession || activeScene === 'console') {
      disconnectObserveWs()
      return
    }
    connectObserveWs(activeSession)
    return () => disconnectObserveWs()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSession, activeScene])

  const handleSessionSelect = (key: string) => {
    setActiveSession(key)
    setStreaming('')
    setThinkingStreaming('')
    setProcessing(false)
    wsSessionId.current = ''
    if (wsReconnectTimer.current) { clearTimeout(wsReconnectTimer.current); wsReconnectTimer.current = null }
    wsRef.current?.close()
    disconnectObserveWs()
    setMobileSessionOpen(false)

    loadSessionMessages(key)

    const meta = sessions.find((s) => s.key === key)
    if (meta?.scene === 'console') {
      const sid = key.replace(/^console:/, '')
      connectWs(sid)
    }
  }

  const handleSceneChange = (scene: SceneType) => {
    setActiveScene(scene)
    wsSessionId.current = ''
    if (wsReconnectTimer.current) { clearTimeout(wsReconnectTimer.current); wsReconnectTimer.current = null }
    wsRef.current?.close()
    disconnectObserveWs()
    setStreaming('')
    setThinkingStreaming('')
    setProcessing(false)

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
      const res = await api<{ session_id: string; conversation_id: string }>('/chat/sessions', {
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
        conversation_id: res.conversation_id,
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
        wsSessionId.current = ''
        if (wsReconnectTimer.current) { clearTimeout(wsReconnectTimer.current); wsReconnectTimer.current = null }
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

  const loadSessionListRef = useRef(loadSessionList)
  loadSessionListRef.current = loadSessionList

  const loadSessionMessagesWithMetaRef = useRef(loadSessionMessagesWithMeta)
  loadSessionMessagesWithMetaRef.current = loadSessionMessagesWithMeta

  // Keep a ref to loadSessionMessages so ws.onmessage always uses the latest version
  // without re-creating the WebSocket every time sessions state updates.
  const loadSessionMessagesRef = useRef(loadSessionMessages)
  loadSessionMessagesRef.current = loadSessionMessages

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
      turnSeq: getNextTurnSeq(prev),
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
    <div className={isMobile ? '-m-4 -mb-20 h-[calc(100dvh-4rem-env(safe-area-inset-bottom,0px))] flex flex-col overflow-hidden' : '-m-6 h-[calc(100vh)] flex flex-col overflow-hidden'}>
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
        {/* Desktop: inline sidebar. Mobile: overlay drawer */}
        {isMobile ? (
          mobileSessionOpen && (
            <>
              {/* Backdrop */}
              <div
                className="fixed inset-0 z-40 bg-black/50"
                onClick={() => setMobileSessionOpen(false)}
              />
              {/* Drawer */}
              <div className="fixed inset-y-0 left-0 z-50 w-72 animate-slide-in-left">
                <SessionSidebar
                  sessions={filteredSessions}
                  activeSession={activeSession}
                  isConsoleScene={isConsole}
                  onSessionSelect={handleSessionSelect}
                  onCreateConsole={handleCreateConsole}
                  onDeleteSession={handleDeleteSession}
                  onRenameSession={handleRenameSession}
                />
              </div>
            </>
          )
        ) : (
          <SessionSidebar
            sessions={filteredSessions}
            activeSession={activeSession}
            isConsoleScene={isConsole}
            onSessionSelect={handleSessionSelect}
            onCreateConsole={handleCreateConsole}
            onDeleteSession={handleDeleteSession}
            onRenameSession={handleRenameSession}
          />
        )}
        <MessageArea
          session={currentMeta}
          turns={turns}
          loading={loadingMessages}
          isConsole={isConsole && !!activeSession}
          streaming={streaming}
          thinkingStreaming={thinkingStreaming}
          sending={sending}
          processing={processing}
          onSend={handleSend}
          onRefresh={handleRefresh}
          isMobile={isMobile}
          onToggleSessionPanel={() => setMobileSessionOpen(v => !v)}
        />
      </div>
    </div>
  )
}
