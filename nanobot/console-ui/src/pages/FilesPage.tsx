import { useEffect, useState, useCallback } from 'react'
import Editor from '@monaco-editor/react'
import { Folder, File, ChevronRight, ChevronDown, Save, RefreshCw } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../stores/auth'
import { cn } from '../lib/utils'

interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  children?: FileNode[]
}

interface FileData {
  path: string
  content: string
  mtime: number
}

function TreeNode({
  node,
  depth,
  selected,
  onSelect,
}: {
  node: FileNode
  depth: number
  selected: string
  onSelect: (path: string) => void
}) {
  const [expanded, setExpanded] = useState(depth < 2)
  const isDir = node.type === 'directory'

  return (
    <div>
      <button
        onClick={() => {
          if (isDir) setExpanded(!expanded)
          else onSelect(node.path)
        }}
        className={cn(
          'flex items-center gap-1.5 w-full text-left py-1 px-2 text-sm rounded hover:bg-[var(--bg-tertiary)] transition-colors',
          selected === node.path && 'bg-[var(--accent)]/10 text-[var(--accent)]',
        )}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {isDir ? (
          expanded ? <ChevronDown className="w-3.5 h-3.5 shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 shrink-0" />
        ) : <span className="w-3.5" />}
        {isDir ? <Folder className="w-4 h-4 text-[var(--warning)] shrink-0" /> : <File className="w-4 h-4 text-[var(--text-secondary)] shrink-0" />}
        <span className="truncate">{node.name}</span>
      </button>
      {isDir && expanded && node.children?.map((child) => (
        <TreeNode key={child.path} node={child} depth={depth + 1} selected={selected} onSelect={onSelect} />
      ))}
    </div>
  )
}

function getLanguage(name: string): string {
  if (name.endsWith('.md')) return 'markdown'
  if (name.endsWith('.json')) return 'json'
  if (name.endsWith('.jsonc')) return 'json'
  if (name.endsWith('.yaml') || name.endsWith('.yml')) return 'yaml'
  if (name.endsWith('.py')) return 'python'
  if (name.endsWith('.sh')) return 'shell'
  if (name.endsWith('.ts') || name.endsWith('.tsx')) return 'typescript'
  if (name.endsWith('.js') || name.endsWith('.jsx')) return 'javascript'
  if (name.endsWith('.pem') || name.endsWith('.crt')) return 'plaintext'
  return 'plaintext'
}

export default function FilesPage() {
  const [root, setRoot] = useState<'workspace' | 'nanobot'>('workspace')
  const [tree, setTree] = useState<FileNode | null>(null)
  const [selectedPath, setSelectedPath] = useState('')
  const [fileData, setFileData] = useState<FileData | null>(null)
  const [editing, setEditing] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const { canEdit } = useAuth()

  const loadTree = useCallback(async () => {
    try {
      const t = await api<FileNode>(`/files/tree?root=${root}`)
      setTree(t)
    } catch {}
  }, [root])

  useEffect(() => { loadTree() }, [loadTree])

  const loadFile = async (path: string) => {
    setSelectedPath(path)
    setMessage(null)
    try {
      const d = await api<FileData>(`/files/read?path=${encodeURIComponent(path)}`)
      setFileData(d)
      setEditing(d.content)
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Load failed' })
    }
  }

  const saveFile = async () => {
    if (!fileData) return
    setSaving(true)
    setMessage(null)
    try {
      const result = await api<FileData>('/files/write', {
        method: 'PUT',
        body: JSON.stringify({ path: fileData.path, content: editing, expected_mtime: fileData.mtime }),
      })
      setFileData({ ...fileData, content: editing, mtime: result.mtime })
      setMessage({ type: 'success', text: 'Saved' })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Save failed' })
    } finally {
      setSaving(false)
    }
  }

  const hasChanges = editing !== fileData?.content

  return (
    <div className="h-[calc(100vh-3rem)] flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Files</h1>
        <div className="flex items-center gap-2">
          <button onClick={loadTree} className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-sm">
            <RefreshCw className="w-4 h-4" /> Reload
          </button>
          {canEdit() && fileData && (
            <button
              onClick={saveFile}
              disabled={!hasChanges || saving}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium disabled:opacity-40"
            >
              <Save className="w-4 h-4" /> {saving ? 'Saving...' : 'Save'}
            </button>
          )}
        </div>
      </div>

      {message && (
        <div className={`mb-3 p-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-[var(--success)]/10 text-[var(--success)]' : 'bg-[var(--danger)]/10 text-[var(--danger)]'}`}>
          {message.text}
        </div>
      )}

      <div className="flex gap-1 mb-3">
        {(['workspace', 'nanobot'] as const).map((r) => (
          <button
            key={r}
            onClick={() => { setRoot(r); setSelectedPath(''); setFileData(null) }}
            className={`px-3 py-1.5 rounded-lg text-sm ${root === r ? 'bg-[var(--accent)] text-white' : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)]'}`}
          >
            {r}
          </button>
        ))}
      </div>

      <div className="flex-1 flex gap-4 min-h-0">
        <div className="w-64 shrink-0 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-y-auto p-2">
          {tree && <TreeNode node={tree} depth={0} selected={selectedPath} onSelect={loadFile} />}
        </div>
        <div className="flex-1 rounded-xl overflow-hidden border border-[var(--border)]">
          {fileData ? (
            <Editor
              height="100%"
              language={getLanguage(selectedPath)}
              theme="vs-dark"
              value={editing}
              onChange={(v) => setEditing(v || '')}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                readOnly: !canEdit(),
                wordWrap: 'on',
                scrollBeyondLastLine: false,
              }}
            />
          ) : (
            <div className="h-full flex items-center justify-center text-[var(--text-secondary)]">
              Select a file to view
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
