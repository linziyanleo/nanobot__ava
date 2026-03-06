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
  const initializedRef = useRef(false)
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

      if (!initializedRef.current && metas.length > 0) {
        initializedRef.current = true
        const firstScene = SCENE_ORDER.find((s) => metas.some((m) => m.scene === s)) || metas[0].scene
        setActiveScene(firstScene)
        const firstSessionInScene = metas.find((m) => m.scene === firstScene)
        if (firstSessionInScene) {
          setActiveSession(firstSessionInScene.filename)
          loadSessionMessages(firstSessionInScene.filename, firstSessionInScene.filepath)
        }
      }
    } catch (err) {
      console.error('Failed to load sessions:', err)
    }
  }, [])

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
    wsRef.current?.close()
    setStreaming('')

    const sceneSessions = sessions.filter((s) => s.scene === scene)
    if (sceneSessions.length > 0) {
      const first = sceneSessions[0]
      setActiveSession(first.filename)
      loadSessionMessages(first.filename, first.filepath)
      if (scene === 'console') {
        const sid = first.filename.replace(/^console_/, '').replace(/\.jsonl$/, '')
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
      setError(msg)
      console.error('Failed to create session:', err)
    }
  }

  const handleDeleteSession = async (filename: string) => {
    const meta = sessions.find((s) => s.filename === filename)
    try {
      if (meta?.scene === 'console') {
        const sid = filename.replace(/^console_/, '').replace(/\.jsonl$/, '')
        await api(`/chat/sessions/${sid}`, { method: 'DELETE' })
      } else if (meta?.filepath) {
        await api('/files/delete', {
          method: 'DELETE',
          body: JSON.stringify({ path: meta.filepath }),
        })
      }
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

  const handleRenameSession = async (filename: string, newName: string) => {
    const meta = sessions.find((s) => s.filename === filename)
    if (!meta?.filepath) return
    try {
      const data = await api<{ content: string }>(`/files/read?path=${encodeURIComponent(meta.filepath)}`)
      const lines = data.content.split('\n')
      if (lines[0]) {
        const parsed = JSON.parse(lines[0])
        if (parsed._type === 'metadata') {
          parsed.key = newName
          lines[0] = JSON.stringify(parsed)
          await api('/files/write', {
            method: 'PUT',
            body: JSON.stringify({ path: meta.filepath, content: lines.join('\n'), expected_mtime: 0 }),
          })
          loadSessionList()
        }
      }
    } catch (err) {
      console.error('Failed to rename session:', err)
    }
  }

  const activeSessionRef = useRef(activeSession)
  activeSessionRef.current = activeSession

  const connectWs = useCallback((sid: string) => {
    wsRef.current?.close()
    const filename = `console_${sid}.jsonl`
    const filepath = `workspace/sessions/${filename}`
    const ws = new WebSocket(wsUrl(`/chat/ws/${sid}`))
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'progress') {
        setStreaming((prev) => prev + data.content)
      } else if (data.type === 'complete') {
        setStreaming('')
        setSending(false)
        loadSessionMessages(filename, filepath)
      }
    }
    ws.onerror = () => setSending(false)
    ws.onclose = () => setSending(false)
    wsRef.current = ws
  }, [loadSessionMessages])

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
          sending={sending}
          onSend={handleSend}
        />
      </div>
    </div>
  )
}
