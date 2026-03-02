import { useEffect, useState } from 'react'
import Editor from '@monaco-editor/react'
import { Save, RefreshCw, Eye } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../stores/auth'

interface ConfigItem {
  name: string
  path: string
  exists: boolean
}

interface ConfigData {
  content: string
  mtime: number
  format: string
}

export default function ConfigPage() {
  const [configs, setConfigs] = useState<ConfigItem[]>([])
  const [selected, setSelected] = useState<string>('')
  const [data, setData] = useState<ConfigData | null>(null)
  const [editing, setEditing] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const { canEdit, isAdmin } = useAuth()

  useEffect(() => {
    api<ConfigItem[]>('/config/list').then((list) => {
      setConfigs(list)
      if (list.length > 0) setSelected(list[0].name)
    })
  }, [])

  useEffect(() => {
    if (selected) loadConfig(selected)
  }, [selected])

  const loadConfig = async (name: string) => {
    try {
      const d = await api<ConfigData>(`/config/${name}`)
      setData(d)
      setEditing(d.content)
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Load failed' })
    }
  }

  const saveConfig = async () => {
    if (!data || !selected) return
    setSaving(true)
    setMessage(null)
    try {
      const result = await api<{ mtime: number }>(`/config/${selected}`, {
        method: 'PUT',
        body: JSON.stringify({ content: editing, mtime: data.mtime }),
      })
      setData({ ...data, content: editing, mtime: result.mtime })
      setMessage({ type: 'success', text: 'Saved successfully' })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Save failed' })
    } finally {
      setSaving(false)
    }
  }

  const revealSecret = async (fieldPath: string) => {
    try {
      const result = await api<{ value: string }>(`/config/${selected}/reveal`, {
        method: 'POST',
        body: JSON.stringify({ field_path: fieldPath }),
      })
      alert(`${fieldPath}: ${result.value}`)
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Reveal failed' })
    }
  }

  const hasChanges = editing !== data?.content

  return (
    <div className="h-[calc(100vh-3rem)]  flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Configuration</h1>
        <div className="flex items-center gap-2">
          {isAdmin() && selected && (
            <button
              onClick={() => {
                const path = prompt('Enter field path (e.g. providers.openai.apiKey):')
                if (path) revealSecret(path)
              }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-sm transition-colors"
            >
              <Eye className="w-4 h-4" />
              Reveal Secret
            </button>
          )}
          <button
            onClick={() => loadConfig(selected)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-sm transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Reload
          </button>
          {canEdit() && (
            <button
              onClick={saveConfig}
              disabled={!hasChanges || saving}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium transition-colors disabled:opacity-40"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Saving...' : 'Save'}
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
        {configs.map((c) => (
          <button
            key={c.name}
            onClick={() => setSelected(c.name)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              selected === c.name
                ? 'bg-[var(--accent)] text-white'
                : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            {c.name}
          </button>
        ))}
      </div>

      <div className="flex-1 rounded-xl overflow-hidden border border-[var(--border)]">
        <Editor
          height="100%"
          language={data?.format === 'jsonc' ? 'json' : data?.format || 'json'}
          theme="vs-dark"
          value={editing}
          onChange={(v) => setEditing(v || '')}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: 'on',
            readOnly: !canEdit(),
            wordWrap: 'on',
            scrollBeyondLastLine: false,
          }}
        />
      </div>
    </div>
  )
}
