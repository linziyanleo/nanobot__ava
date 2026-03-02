import { useEffect, useRef, useState } from 'react'
import { Plus, Send, Trash2, MessageSquare } from 'lucide-react'
import { api, wsUrl } from '../api/client'
import { useAuth } from '../stores/auth'
import { cn } from '../lib/utils'

interface Session {
  session_id: string
  title: string
  created_at: string
  message_count: number
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
}

export default function ChatPage() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [activeSession, setActiveSession] = useState<string>('')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState('')
  const [sending, setSending] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  useAuth()

  useEffect(() => {
    loadSessions()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming])

  const loadSessions = async () => {
    const list = await api<Session[]>('/chat/sessions')
    setSessions(list)
  }

  const createSession = async () => {
    const title = `Chat ${sessions.length + 1}`
    const res = await api<{ session_id: string }>('/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ title }),
    })
    await loadSessions()
    selectSession(res.session_id)
  }

  const selectSession = async (sid: string) => {
    setActiveSession(sid)
    setStreaming('')
    wsRef.current?.close()
    const history = await api<Message[]>(`/chat/sessions/${sid}/history`)
    setMessages(history)
    connectWs(sid)
  }

  const deleteSession = async (sid: string) => {
    await api(`/chat/sessions/${sid}`, { method: 'DELETE' })
    if (activeSession === sid) {
      setActiveSession('')
      setMessages([])
      wsRef.current?.close()
    }
    loadSessions()
  }

  const connectWs = (sid: string) => {
    const ws = new WebSocket(wsUrl(`/chat/ws/${sid}`))
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'progress') {
        setStreaming((prev) => prev + data.content)
      } else if (data.type === 'complete') {
        setStreaming('')
        setMessages((prev) => [...prev, { role: 'assistant', content: data.content }])
        setSending(false)
      }
    }
    ws.onerror = () => setSending(false)
    ws.onclose = () => setSending(false)
    wsRef.current = ws
  }

  const sendMessage = () => {
    if (!input.trim() || !wsRef.current || sending) return
    const msg = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: msg }])
    setStreaming('')
    setSending(true)
    wsRef.current.send(JSON.stringify({ content: msg }))
  }

  return (
    <div className="h-[calc(100vh-3rem)] flex">
      {/* Session list */}
      <div className="w-60 shrink-0 bg-[var(--bg-secondary)] border-r border-[var(--border)] flex flex-col rounded-l-xl">
        <div className="p-3 border-b border-[var(--border)]">
          <button
            onClick={createSession}
            className="flex items-center gap-2 w-full px-3 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium"
          >
            <Plus className="w-4 h-4" /> New Chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {sessions.map((s) => (
            <div
              key={s.session_id}
              className={cn(
                'flex items-center justify-between group px-3 py-2 rounded-lg text-sm cursor-pointer transition-colors',
                activeSession === s.session_id
                  ? 'bg-[var(--accent)]/10 text-[var(--accent)]'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]',
              )}
              onClick={() => selectSession(s.session_id)}
            >
              <div className="flex items-center gap-2 truncate">
                <MessageSquare className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate">{s.title}</span>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); deleteSession(s.session_id) }}
                className="opacity-0 group-hover:opacity-100 p-1 text-[var(--text-secondary)] hover:text-[var(--danger)]"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          {sessions.length === 0 && (
            <p className="text-center text-xs text-[var(--text-secondary)] py-8">No sessions yet</p>
          )}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col bg-[var(--bg-primary)] rounded-r-xl">
        {activeSession ? (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((msg, i) => (
                <div key={i} className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                  <div
                    className={cn(
                      'max-w-[75%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed',
                      msg.role === 'user'
                        ? 'bg-[var(--accent)] text-white rounded-br-md'
                        : 'bg-[var(--bg-secondary)] text-[var(--text-primary)] rounded-bl-md border border-[var(--border)]',
                    )}
                  >
                    <pre className="whitespace-pre-wrap font-[inherit]">{msg.content}</pre>
                  </div>
                </div>
              ))}
              {streaming && (
                <div className="flex justify-start">
                  <div className="max-w-[75%] px-4 py-2.5 rounded-2xl rounded-bl-md bg-[var(--bg-secondary)] border border-[var(--border)] text-sm">
                    <pre className="whitespace-pre-wrap font-[inherit]">{streaming}</pre>
                    <span className="inline-block w-2 h-4 bg-[var(--accent)] animate-pulse ml-0.5" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="p-4 border-t border-[var(--border)]">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                  placeholder="Type a message..."
                  disabled={sending}
                  className="flex-1 px-4 py-2.5 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)] disabled:opacity-50"
                />
                <button
                  onClick={sendMessage}
                  disabled={!input.trim() || sending}
                  className="px-4 py-2.5 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white disabled:opacity-40"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-[var(--text-secondary)]">
            <div className="text-center">
              <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>Select or create a chat session</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
