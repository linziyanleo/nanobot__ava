import { useEffect, useState, useCallback } from 'react'
import Editor from '@monaco-editor/react'
import {
  Brain, BookOpen, ImageIcon, ChevronRight, ChevronLeft,
  Save, RefreshCw, Calendar, Search, X, AlertCircle, Pencil, Trash2,
  Globe, User, Check,
} from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../stores/auth'
import { cn } from '../lib/utils'
import yaml from 'js-yaml'

// ── Types ──────────────────────────────────────────────────────────────────

interface FileData {
  path: string
  content: string
  mtime: number
}

interface Person {
  key: string
  displayName: string
}

interface MediaRecord {
  id: string
  timestamp: string
  prompt: string
  reference_image: string | null
  output_images: string[]
  output_text: string
  model: string
  status: string
  error: string | null
}

interface MediaResponse {
  records: MediaRecord[]
  total: number
  page: number
  size: number
}

interface DiaryEntry {
  date: string
  filename: string
}

// ── Helper Functions ───────────────────────────────────────────────────────

function parseHistoryEntries(content: string): Array<{ date: string; text: string; startLine: number; endLine: number }> {
  const entries: Array<{ date: string; text: string; startLine: number; endLine: number }> = []
  const lines = content.split('\n')
  let currentEntry: { date: string; text: string; startLine: number; endLine: number } | null = null

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const match = line.match(/^\[(\d{4}-\d{2}-\d{2}[^\]]*)\](.*)/)
    if (match) {
      if (currentEntry) {
        currentEntry.endLine = i - 1
        entries.push(currentEntry)
      }
      currentEntry = { date: match[1], text: match[2].trim(), startLine: i, endLine: i }
    } else if (currentEntry && line.trim()) {
      currentEntry.text += '\n' + line
      currentEntry.endLine = i
    }
  }
  if (currentEntry) {
    currentEntry.endLine = lines.length - 1
    entries.push(currentEntry)
  }
  return entries.reverse()
}

function imageUrl(path: string): string {
  const token = localStorage.getItem('token')
  const filename = path.split('/').pop() || path
  const base = `/api/media/images/${filename}`
  return token ? `${base}?token=${token}` : base
}

// ── Memory Scope Menu ──────────────────────────────────────────────────────

type MemoryScope = { type: 'global' } | { type: 'person'; key: string; displayName: string }

function ScopeMenu({ 
  persons, 
  scope, 
  onSelect 
}: { 
  persons: Person[]
  scope: MemoryScope
  onSelect: (scope: MemoryScope) => void 
}) {
  return (
    <div className="w-48 shrink-0 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-[var(--border)]">
        <h3 className="text-sm font-semibold">记忆范围</h3>
      </div>
      <div className="overflow-y-auto max-h-[calc(100vh-16rem)]">
        {/* Global */}
        <button
          onClick={() => onSelect({ type: 'global' })}
          className={cn(
            'w-full flex items-center gap-2 px-4 py-2.5 text-left text-sm transition-colors',
            scope.type === 'global'
              ? 'bg-[var(--accent)] text-white'
              : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]'
          )}
        >
          <Globe className="w-4 h-4" />
          全局记忆
        </button>
        
        {/* Persons */}
        {persons.length > 0 && (
          <div className="px-3 py-2 text-xs text-[var(--text-secondary)] font-medium uppercase tracking-wide">
            Person 记忆
          </div>
        )}
        {persons.map(p => (
          <button
            key={p.key}
            onClick={() => onSelect({ type: 'person', key: p.key, displayName: p.displayName })}
            className={cn(
              'w-full flex items-center gap-2 px-4 py-2.5 text-left text-sm transition-colors',
              scope.type === 'person' && scope.key === p.key
                ? 'bg-[var(--accent)] text-white'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]'
            )}
          >
            <User className="w-4 h-4" />
            {p.displayName}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Memory Content (Memory + History tabs) ─────────────────────────────────

function MemoryContent({ scope }: { scope: MemoryScope }) {
  const [activeTab, setActiveTab] = useState<'memory' | 'history'>('memory')
  const [memoryData, setMemoryData] = useState<FileData | null>(null)
  const [historyData, setHistoryData] = useState<FileData | null>(null)
  const [memoryEdit, setMemoryEdit] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [editingEntry, setEditingEntry] = useState<number | null>(null)
  const [editingText, setEditingText] = useState('')
  const { canEdit } = useAuth()

  const basePath = scope.type === 'global' 
    ? 'workspace/memory' 
    : `workspace/memory/persons/${scope.key}`

  const loadFiles = useCallback(async () => {
    setMessage(null)
    try {
      const [mem, hist] = await Promise.all([
        api<FileData>(`/files/read?path=${basePath}/MEMORY.md`).catch(() => null),
        api<FileData>(`/files/read?path=${basePath}/HISTORY.md`).catch(() => null),
      ])
      setMemoryData(mem)
      setMemoryEdit(mem?.content || '')
      setHistoryData(hist)
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '加载失败' })
    }
  }, [basePath])

  useEffect(() => { 
    loadFiles()
    setEditingEntry(null)
  }, [loadFiles])

  const saveMemory = async () => {
    if (!memoryData) return
    setSaving(true)
    setMessage(null)
    try {
      const result = await api<FileData>('/files/write', {
        method: 'PUT',
        body: JSON.stringify({ path: memoryData.path, content: memoryEdit, expected_mtime: memoryData.mtime }),
      })
      setMemoryData({ ...memoryData, content: memoryEdit, mtime: result.mtime })
      setMessage({ type: 'success', text: '保存成功' })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '保存失败' })
    } finally {
      setSaving(false)
    }
  }

  const saveHistoryEntry = async (idx: number) => {
    if (!historyData) return
    const entries = parseHistoryEntries(historyData.content)
    const entry = entries[idx]
    if (!entry) return

    // Rebuild content with edited entry
    const lines = historyData.content.split('\n')
    const newEntryText = `[${entry.date}] ${editingText}`
    const newLines = [
      ...lines.slice(0, entry.startLine),
      newEntryText,
      ...lines.slice(entry.endLine + 1)
    ]
    const newContent = newLines.join('\n')

    setSaving(true)
    setMessage(null)
    try {
      const result = await api<FileData>('/files/write', {
        method: 'PUT',
        body: JSON.stringify({ path: historyData.path, content: newContent, expected_mtime: historyData.mtime }),
      })
      setHistoryData({ ...historyData, content: newContent, mtime: result.mtime })
      setEditingEntry(null)
      setMessage({ type: 'success', text: '保存成功' })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '保存失败' })
    } finally {
      setSaving(false)
    }
  }

  const startEditEntry = (idx: number, text: string) => {
    setEditingEntry(idx)
    setEditingText(text)
  }

  const historyEntries = historyData ? parseHistoryEntries(historyData.content) : []
  const memoryChanged = memoryEdit !== memoryData?.content

  const scopeLabel = scope.type === 'global' ? '全局' : scope.displayName

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Tabs */}
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4">
        <div className="flex gap-1">
          <button
            onClick={() => setActiveTab('memory')}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors',
              activeTab === 'memory'
                ? 'text-[var(--accent)] border-[var(--accent)]'
                : 'text-[var(--text-secondary)] border-transparent hover:text-[var(--text-primary)]'
            )}
          >
            <Brain className="w-4 h-4" />
            Memory
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors',
              activeTab === 'history'
                ? 'text-[var(--accent)] border-[var(--accent)]'
                : 'text-[var(--text-secondary)] border-transparent hover:text-[var(--text-primary)]'
            )}
          >
            <BookOpen className="w-4 h-4" />
            History
            {historyEntries.length > 0 && (
              <span className="text-xs text-[var(--text-secondary)]">({historyEntries.length})</span>
            )}
          </button>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--text-secondary)]">{scopeLabel}</span>
          <button onClick={loadFiles} title="刷新" className="p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {message && (
        <div className={`mx-4 mt-3 p-2 rounded-lg text-sm ${message.type === 'success' ? 'bg-[var(--success)]/10 text-[var(--success)]' : 'bg-[var(--danger)]/10 text-[var(--danger)]'}`}>
          {message.text}
        </div>
      )}

      {/* Memory Tab */}
      {activeTab === 'memory' && (
        <div className="flex-1 flex flex-col min-h-0 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold">MEMORY.md</h3>
            {canEdit() && memoryData && (
              <button
                onClick={saveMemory}
                disabled={!memoryChanged || saving}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-xs font-medium disabled:opacity-40"
              >
                <Save className="w-3.5 h-3.5" /> {saving ? '保存中...' : '保存'}
              </button>
            )}
          </div>
          <div className="flex-1 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden">
            {memoryData ? (
              <Editor
                height="100%"
                language="markdown"
                theme="vs-dark"
                value={memoryEdit}
                onChange={(v) => setMemoryEdit(v || '')}
                options={{ minimap: { enabled: false }, fontSize: 13, readOnly: !canEdit(), wordWrap: 'on', scrollBeyondLastLine: false }}
              />
            ) : (
              <div className="h-full flex items-center justify-center text-[var(--text-secondary)]">
                文件不存在
              </div>
            )}
          </div>
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {historyEntries.length === 0 ? (
            <div className="flex items-center justify-center h-32 text-[var(--text-secondary)]">
              暂无历史记录
            </div>
          ) : (
            historyEntries.map((entry, idx) => (
              <div key={idx} className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg overflow-hidden">
                <div className="flex items-start justify-between px-4 py-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs text-[var(--accent)] font-mono shrink-0">[{entry.date}]</span>
                    </div>
                    {editingEntry === idx ? (
                      <textarea
                        value={editingText}
                        onChange={(e) => setEditingText(e.target.value)}
                        placeholder="编辑记录内容..."
                        className="w-full p-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-sm text-[var(--text-primary)] resize-y min-h-[80px]"
                        autoFocus
                      />
                    ) : (
                      <p className="text-sm text-[var(--text-primary)] whitespace-pre-wrap">{entry.text}</p>
                    )}
                  </div>
                  {canEdit() && (
                    <div className="flex items-center gap-1 ml-3 shrink-0">
                      {editingEntry === idx ? (
                        <>
                          <button
                            onClick={() => saveHistoryEntry(idx)}
                            disabled={saving}
                            title="保存"
                            className="p-1.5 rounded-lg text-[var(--success)] hover:bg-[var(--success)]/10"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setEditingEntry(null)}
                            title="取消"
                            className="p-1.5 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => startEditEntry(idx, entry.text)}
                          title="编辑"
                          className="p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

// ── Diary Tab ──────────────────────────────────────────────────────────────

function DiaryTab() {
  const [diaries, setDiaries] = useState<DiaryEntry[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [content, setContent] = useState<FileData | null>(null)
  const [editing, setEditing] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const { canEdit } = useAuth()

  const loadDiaryList = useCallback(async () => {
    try {
      const tree = await api<{ children?: Array<{ name: string; path: string }> }>('/files/tree?root=workspace')
      const diaryFolder = tree.children?.find(c => c.name === 'diary')
      if (diaryFolder && 'children' in diaryFolder) {
        const entries: DiaryEntry[] = ((diaryFolder as { children?: Array<{ name: string }> }).children || [])
          .filter(f => f.name.endsWith('.md'))
          .map(f => ({ date: f.name.replace('.md', ''), filename: f.name }))
          .sort((a, b) => b.date.localeCompare(a.date))
        setDiaries(entries)
        if (entries.length > 0 && !selected) {
          setSelected(entries[0].date)
        }
      }
    } catch {}
  }, [selected])

  useEffect(() => { loadDiaryList() }, [loadDiaryList])

  useEffect(() => {
    if (!selected) return
    api<FileData>(`/files/read?path=workspace/diary/${selected}.md`)
      .then(data => {
        setContent(data)
        setEditing(data.content)
      })
      .catch(() => setContent(null))
  }, [selected])

  const saveFile = async () => {
    if (!content) return
    setSaving(true)
    setMessage(null)
    try {
      const result = await api<FileData>('/files/write', {
        method: 'PUT',
        body: JSON.stringify({ path: content.path, content: editing, expected_mtime: content.mtime }),
      })
      setContent({ ...content, content: editing, mtime: result.mtime })
      setMessage({ type: 'success', text: '保存成功' })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '保存失败' })
    } finally {
      setSaving(false)
    }
  }

  const hasChanges = editing !== content?.content

  return (
    <div className="flex gap-4 h-[calc(100vh-14rem)]">
      <div className="w-48 shrink-0 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--border)]">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Calendar className="w-4 h-4 text-[var(--accent)]" />
            日记列表
          </h3>
        </div>
        <div className="overflow-y-auto max-h-[calc(100%-3rem)]">
          {diaries.map(d => (
            <button
              key={d.date}
              onClick={() => setSelected(d.date)}
              className={cn(
                'w-full px-4 py-2.5 text-left text-sm transition-colors',
                selected === d.date
                  ? 'bg-[var(--accent)] text-white'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]'
              )}
            >
              {d.date}
            </button>
          ))}
          {diaries.length === 0 && (
            <div className="px-4 py-8 text-center text-[var(--text-secondary)] text-sm">暂无日记</div>
          )}
        </div>
      </div>

      <div className="flex-1 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--border)]">
          <h3 className="text-sm font-semibold">{selected ? `${selected} 日记` : '选择日期'}</h3>
          {canEdit() && content && (
            <button
              onClick={saveFile}
              disabled={!hasChanges || saving}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-xs font-medium disabled:opacity-40"
            >
              <Save className="w-3.5 h-3.5" /> {saving ? '保存中...' : '保存'}
            </button>
          )}
        </div>
        {message && (
          <div className={`mx-4 mt-3 p-2 rounded-lg text-xs ${message.type === 'success' ? 'bg-[var(--success)]/10 text-[var(--success)]' : 'bg-[var(--danger)]/10 text-[var(--danger)]'}`}>
            {message.text}
          </div>
        )}
        <div className="flex-1">
          {content ? (
            <Editor
              height="100%"
              language="markdown"
              theme="vs-dark"
              value={editing}
              onChange={(v) => setEditing(v || '')}
              options={{ minimap: { enabled: false }, fontSize: 13, readOnly: !canEdit(), wordWrap: 'on', scrollBeyondLastLine: false }}
            />
          ) : (
            <div className="h-full flex items-center justify-center text-[var(--text-secondary)]">
              {selected ? '加载中...' : '请选择日期查看日记'}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Generated Images Tab ───────────────────────────────────────────────────

function GeneratedImagesTab() {
  const [data, setData] = useState<MediaResponse | null>(null)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [selected, setSelected] = useState<MediaRecord | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const { canEdit } = useAuth()

  const loadRecords = useCallback(async () => {
    const params = new URLSearchParams({ page: String(page), size: '18' })
    if (search) params.set('search', search)
    const res = await api<MediaResponse>(`/media/records?${params}`)
    setData(res)
  }, [page, search])

  useEffect(() => { loadRecords() }, [loadRecords])

  const handleSearch = () => { setSearch(searchInput); setPage(1) }
  const clearSearch = () => { setSearchInput(''); setSearch(''); setPage(1) }

  const handleDelete = async (record: MediaRecord, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(`确定删除这条生图记录吗？\n\n${record.prompt.slice(0, 100)}...`)) return
    setDeleting(record.id)
    setMessage(null)
    try {
      await api(`/media/records/${record.id}`, { method: 'DELETE' })
      setMessage({ type: 'success', text: '删除成功' })
      loadRecords()
      if (selected?.id === record.id) setSelected(null)
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '删除失败' })
    } finally {
      setDeleting(null)
    }
  }

  const totalPages = data ? Math.ceil(data.total / data.size) : 0

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="relative">
            <input
              type="text"
              placeholder="搜索 prompt..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="pl-9 pr-8 py-1.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] text-sm text-[var(--text-primary)] w-56"
            />
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
            {searchInput && (
              <button onClick={clearSearch} title="清除搜索" className="absolute right-2 top-1/2 -translate-y-1/2">
                <X className="w-3.5 h-3.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)]" />
              </button>
            )}
          </div>
          <span className="text-sm text-[var(--text-secondary)]">{data?.total ?? 0} 条记录</span>
        </div>
      </div>

      {message && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-[var(--success)]/10 text-[var(--success)]' : 'bg-[var(--danger)]/10 text-[var(--danger)]'}`}>
          {message.text}
        </div>
      )}

      {data?.records.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-[var(--text-secondary)]">
          <ImageIcon className="w-12 h-12 mb-3 opacity-30" />
          <p className="text-sm">{search ? '没有匹配的记录' : '暂无图片生成记录'}</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
          {data?.records.map((record) => (
            <div
              key={record.id}
              onClick={() => setSelected(record)}
              className="group cursor-pointer bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden hover:border-[var(--accent)] transition-all duration-200 relative"
            >
              {canEdit() && (
                <button
                  onClick={(e) => handleDelete(record, e)}
                  disabled={deleting === record.id}
                  className="absolute top-2 left-2 z-10 p-1.5 rounded-lg bg-black/60 text-white opacity-0 group-hover:opacity-100 hover:bg-[var(--danger)] transition-all"
                  title="删除"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
              <div className="aspect-square bg-[var(--bg-tertiary)] relative overflow-hidden">
                {record.output_images.length > 0 ? (
                  <img src={imageUrl(record.output_images[0])} alt={record.prompt} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" loading="lazy" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <AlertCircle className="w-8 h-8 text-[var(--danger)] opacity-50" />
                  </div>
                )}
                {record.reference_image && (
                  <div className="absolute top-2 right-2 bg-[var(--accent)] text-white rounded-full p-1" title="编辑模式">
                    <Pencil className="w-3 h-3" />
                  </div>
                )}
                {record.status === 'error' && (
                  <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                    <span className="text-xs text-[var(--danger)] font-medium px-2 py-1 bg-black/60 rounded">失败</span>
                  </div>
                )}
              </div>
              <div className="p-3">
                <p className="text-xs text-[var(--text-primary)] line-clamp-2 leading-relaxed">{record.prompt}</p>
                <p className="text-[10px] text-[var(--text-secondary)] mt-1.5">{new Date(record.timestamp).toLocaleString()}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <p className="text-sm text-[var(--text-secondary)]">共 {data?.total} 条记录</p>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1} title="上一页" className="p-2 rounded-lg bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-30">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-sm">{page} / {totalPages}</span>
            <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page >= totalPages} title="下一页" className="p-2 rounded-lg bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-30">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {selected && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-6" onClick={() => setSelected(null)}>
          <div className="bg-[var(--bg-primary)] border border-[var(--border)] rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
            {selected.output_images.length > 0 && (
              <div className="bg-[var(--bg-tertiary)] flex items-center justify-center p-4">
                <img src={imageUrl(selected.output_images[0])} alt={selected.prompt} className="max-h-[50vh] rounded-lg object-contain" />
              </div>
            )}
            <div className="p-6 space-y-4">
              <div>
                <label className="text-xs font-medium text-[var(--text-secondary)] uppercase">Prompt</label>
                <p className="mt-1 text-sm text-[var(--text-primary)] leading-relaxed">{selected.prompt}</p>
              </div>
              {selected.reference_image && (
                <div>
                  <label className="text-xs font-medium text-[var(--text-secondary)] uppercase">参考图片</label>
                  <p className="mt-1 text-xs text-[var(--text-secondary)] font-mono break-all">{selected.reference_image}</p>
                </div>
              )}
              {selected.output_text && (
                <div>
                  <label className="text-xs font-medium text-[var(--text-secondary)] uppercase">模型输出文本</label>
                  <p className="mt-1 text-sm text-[var(--text-primary)]">{selected.output_text}</p>
                </div>
              )}
              {selected.error && (
                <div>
                  <label className="text-xs font-medium text-[var(--danger)] uppercase">错误</label>
                  <p className="mt-1 text-sm text-[var(--danger)]">{selected.error}</p>
                </div>
              )}
              <div className="flex items-center gap-6 text-xs text-[var(--text-secondary)]">
                <span>模型: {selected.model}</span>
                <span>状态: <span className={selected.status === 'success' ? 'text-[var(--success)]' : 'text-[var(--danger)]'}>{selected.status}</span></span>
                <span>{new Date(selected.timestamp).toLocaleString()}</span>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                {canEdit() && (
                  <button onClick={(e) => { handleDelete(selected, e); setSelected(null) }} disabled={deleting === selected.id} className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--danger)]/10 text-[var(--danger)] hover:bg-[var(--danger)]/20 text-sm font-medium">
                    <Trash2 className="w-4 h-4" /> 删除
                  </button>
                )}
                <button onClick={() => setSelected(null)} className="px-4 py-2 rounded-lg bg-[var(--bg-secondary)] text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors">
                  关闭
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────

const TABS = [
  { id: 'memory', label: '记忆', icon: Brain },
  { id: 'diary', label: '日记', icon: BookOpen },
  { id: 'images', label: '生成图片', icon: ImageIcon },
] as const

type TabId = typeof TABS[number]['id']

export default function MemoryPage() {
  const [activeTab, setActiveTab] = useState<TabId>('memory')
  const [persons, setPersons] = useState<Person[]>([])
  const [scope, setScope] = useState<MemoryScope>({ type: 'global' })

  // Load persons from identity_map.yaml
  useEffect(() => {
    api<FileData>('/files/read?path=workspace/memory/identity_map.yaml')
      .then(data => {
        const parsed = yaml.load(data.content) as { persons?: Record<string, { display_name?: string }> }
        if (parsed?.persons) {
          const list = Object.entries(parsed.persons).map(([key, val]) => ({
            key,
            displayName: val.display_name || key,
          }))
          setPersons(list)
        }
      })
      .catch(() => {})
  }, [])

  return (
    <div className="h-[calc(100vh-3rem)] flex flex-col">
      <div className="mb-4">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Brain className="w-6 h-6 text-[var(--accent)]" />
          记忆管理
        </h1>
        <p className="text-[var(--text-secondary)] text-sm mt-1">管理全局记忆、个人记忆、日记和生成图片</p>
      </div>

      {/* Top Tabs */}
      <div className="flex gap-1 mb-4 border-b border-[var(--border)]">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px',
              activeTab === tab.id
                ? 'text-[var(--accent)] border-[var(--accent)]'
                : 'text-[var(--text-secondary)] border-transparent hover:text-[var(--text-primary)]'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'memory' && (
        <div className="flex-1 flex gap-4 min-h-0">
          <ScopeMenu persons={persons} scope={scope} onSelect={setScope} />
          <div className="flex-1 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden flex flex-col min-h-0">
            <MemoryContent scope={scope} />
          </div>
        </div>
      )}
      {activeTab === 'diary' && <DiaryTab />}
      {activeTab === 'images' && <GeneratedImagesTab />}
    </div>
  )
}
