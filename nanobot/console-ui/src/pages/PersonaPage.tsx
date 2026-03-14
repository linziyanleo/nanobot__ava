import { useEffect, useState, useCallback } from 'react'
import Editor from '@monaco-editor/react'
import { UserCog, Save, RefreshCw } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../stores/auth'
import { cn } from '../lib/utils'

interface FileData {
  path: string
  content: string
  mtime: number
}

const PERSONA_FILES = [
  { key: 'agents', name: 'AGENTS.md', description: 'Agent 指令配置' },
  { key: 'soul', name: 'SOUL.md', description: '人格设定' },
  { key: 'tools', name: 'TOOLS.md', description: '工具说明' },
  { key: 'user', name: 'USER.md', description: '用户信息' },
] as const

type FileKey = typeof PERSONA_FILES[number]['key']

export default function PersonaPage() {
  const [files, setFiles] = useState<Record<FileKey, FileData | null>>({
    agents: null,
    soul: null,
    tools: null,
    user: null,
  })
  const [edits, setEdits] = useState<Record<FileKey, string>>({
    agents: '',
    soul: '',
    tools: '',
    user: '',
  })
  const [saving, setSaving] = useState<FileKey | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const { canEdit } = useAuth()

  const loadFiles = useCallback(async () => {
    try {
      const results = await Promise.all(
        PERSONA_FILES.map(f =>
          api<FileData>(`/files/read?path=workspace/${f.name}`)
            .then(data => ({ key: f.key, data }))
            .catch(() => ({ key: f.key, data: null }))
        )
      )
      const newFiles: Record<string, FileData | null> = {}
      const newEdits: Record<string, string> = {}
      for (const { key, data } of results) {
        newFiles[key] = data
        newEdits[key] = data?.content || ''
      }
      setFiles(newFiles as Record<FileKey, FileData | null>)
      setEdits(newEdits as Record<FileKey, string>)
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '加载失败' })
    }
  }, [])

  useEffect(() => { loadFiles() }, [loadFiles])

  const saveFile = async (key: FileKey) => {
    const file = files[key]
    const content = edits[key]
    if (!file) return

    setSaving(key)
    setMessage(null)
    try {
      const result = await api<FileData>('/files/write', {
        method: 'PUT',
        body: JSON.stringify({ path: file.path, content, expected_mtime: file.mtime }),
      })
      setFiles(prev => ({ ...prev, [key]: { ...file, content, mtime: result.mtime } }))
      setMessage({ type: 'success', text: `${PERSONA_FILES.find(f => f.key === key)?.name} 保存成功` })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '保存失败' })
    } finally {
      setSaving(null)
    }
  }

  const hasChanges = (key: FileKey) => edits[key] !== files[key]?.content

  return (
    <div className="h-[calc(100vh-3rem)] flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <UserCog className="w-6 h-6 text-[var(--accent)]" />
            人物设定
          </h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">管理 Agent 的核心配置文件</p>
        </div>
        <button
          onClick={loadFiles}
          title="刷新所有文件"
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-sm"
        >
          <RefreshCw className="w-4 h-4" /> 刷新
        </button>
      </div>

      {message && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-[var(--success)]/10 text-[var(--success)]' : 'bg-[var(--danger)]/10 text-[var(--danger)]'}`}>
          {message.text}
        </div>
      )}

      {/* 2x2 Grid Layout */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-0">
        {PERSONA_FILES.map(file => (
          <div
            key={file.key}
            className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden flex flex-col min-h-0"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--border)] shrink-0">
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-[var(--text-primary)] truncate">{file.name}</h3>
                <p className="text-xs text-[var(--text-secondary)]">{file.description}</p>
              </div>
              {canEdit() && files[file.key] && (
                <button
                  onClick={() => saveFile(file.key)}
                  disabled={!hasChanges(file.key) || saving === file.key}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0',
                    hasChanges(file.key)
                      ? 'bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white'
                      : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]',
                    'disabled:opacity-40'
                  )}
                >
                  <Save className="w-3.5 h-3.5" />
                  {saving === file.key ? '保存中...' : hasChanges(file.key) ? '保存' : '已保存'}
                </button>
              )}
            </div>
            {/* Editor */}
            <div className="flex-1 min-h-0">
              {files[file.key] ? (
                <Editor
                  height="100%"
                  language="markdown"
                  theme="vs-dark"
                  value={edits[file.key]}
                  onChange={(v) => setEdits(prev => ({ ...prev, [file.key]: v || '' }))}
                  options={{
                    minimap: { enabled: false },
                    fontSize: 12,
                    readOnly: !canEdit(),
                    wordWrap: 'on',
                    scrollBeyondLastLine: false,
                    lineNumbers: 'off',
                    folding: false,
                    glyphMargin: false,
                    lineDecorationsWidth: 0,
                    lineNumbersMinChars: 0,
                  }}
                />
              ) : (
                <div className="h-full flex items-center justify-center text-[var(--text-secondary)] text-sm">
                  文件不存在
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
