import { useEffect, useState, useCallback } from 'react'
import Editor from '@monaco-editor/react'
import {
  Wrench, Puzzle, Plus, RefreshCw, Save, GitBranch, FolderOpen, Trash2, X,
  Package, Pencil,
} from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../stores/auth'
import { cn } from '../lib/utils'

// ── Types ──────────────────────────────────────────────────────────────────

interface ToolInfo {
  name: string
  class: string
  description: string
  file: string
}

interface SkillInfo {
  name: string
  source: 'workspace' | 'builtin'
  path: string
  enabled: boolean
  description: string
  always: boolean
}

interface FileData {
  path: string
  content: string
  mtime: number
}

// ── Tools Section ──────────────────────────────────────────────────────────

function ToolsSection() {
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [toolsDoc, setToolsDoc] = useState<FileData | null>(null)
  const [docEdit, setDocEdit] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const { canEdit } = useAuth()

  const loadTools = useCallback(async () => {
    try {
      const [toolsRes, docRes] = await Promise.all([
        api<{ tools: ToolInfo[] }>('/skills/tools'),
        api<FileData>('/files/read?path=workspace/TOOLS.md').catch(() => null),
      ])
      setTools(toolsRes.tools)
      setToolsDoc(docRes)
      setDocEdit(docRes?.content || '')
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '加载失败' })
    }
  }, [])

  useEffect(() => { loadTools() }, [loadTools])

  const saveDoc = async () => {
    if (!toolsDoc) return
    setSaving(true)
    setMessage(null)
    try {
      const result = await api<FileData>('/files/write', {
        method: 'PUT',
        body: JSON.stringify({ path: toolsDoc.path, content: docEdit, expected_mtime: toolsDoc.mtime }),
      })
      setToolsDoc({ ...toolsDoc, content: docEdit, mtime: result.mtime })
      setMessage({ type: 'success', text: 'TOOLS.md 保存成功' })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '保存失败' })
    } finally {
      setSaving(false)
    }
  }

  const docChanged = docEdit !== toolsDoc?.content

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Wrench className="w-5 h-5 text-[var(--accent)]" />
          内置工具
          <span className="text-sm text-[var(--text-secondary)] font-normal">({tools.length} 个)</span>
        </h2>
        <button
          onClick={loadTools}
          title="刷新"
          className="p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {message && (
        <div className={`p-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-[var(--success)]/10 text-[var(--success)]' : 'bg-[var(--danger)]/10 text-[var(--danger)]'}`}>
          {message.text}
        </div>
      )}

      {/* Tools Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {tools.map(tool => (
          <div
            key={tool.name}
            className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-4 hover:border-[var(--accent)]/50 transition-all"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-[var(--accent)]/10 text-[var(--accent)]">
                  <Wrench className="w-4 h-4" />
                </div>
                <span className="font-mono text-sm font-medium">{tool.name}</span>
              </div>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-2 line-clamp-2">{tool.description}</p>
            <p className="text-[10px] text-[var(--text-secondary)]/60 mt-2 font-mono">{tool.file}</p>
          </div>
        ))}
      </div>

      {/* TOOLS.md Editor */}
      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
          <div className="flex items-center gap-2">
            <Pencil className="w-4 h-4 text-[var(--warning)]" />
            <span className="text-sm font-semibold">TOOLS.md</span>
            <span className="text-xs text-[var(--text-secondary)]">工具文档</span>
          </div>
          {canEdit() && toolsDoc && (
            <button
              onClick={saveDoc}
              disabled={!docChanged || saving}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-xs font-medium disabled:opacity-40"
            >
              <Save className="w-3.5 h-3.5" /> {saving ? '保存中...' : '保存'}
            </button>
          )}
        </div>
        <div className="h-64">
          {toolsDoc ? (
            <Editor
              height="100%"
              language="markdown"
              theme="vs-dark"
              value={docEdit}
              onChange={(v) => setDocEdit(v || '')}
              options={{ minimap: { enabled: false }, fontSize: 13, readOnly: !canEdit(), wordWrap: 'on', scrollBeyondLastLine: false }}
            />
          ) : (
            <div className="h-full flex items-center justify-center text-[var(--text-secondary)]">
              TOOLS.md 文件不存在
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Skills Section ─────────────────────────────────────────────────────────

function SkillsSection() {
  const [skills, setSkills] = useState<SkillInfo[]>([])
  const [showInstall, setShowInstall] = useState<'git' | 'path' | null>(null)
  const [gitUrl, setGitUrl] = useState('')
  const [localPath, setLocalPath] = useState('')
  const [skillName, setSkillName] = useState('')
  const [installing, setInstalling] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const { canEdit, isAdmin } = useAuth()

  const loadSkills = useCallback(async () => {
    try {
      const res = await api<{ skills: SkillInfo[] }>('/skills/list')
      setSkills(res.skills)
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '加载失败' })
    }
  }, [])

  useEffect(() => { loadSkills() }, [loadSkills])

  const installFromGit = async () => {
    if (!gitUrl.trim()) return
    setInstalling(true)
    setMessage(null)
    try {
      await api('/skills/install/git', {
        method: 'POST',
        body: JSON.stringify({ git_url: gitUrl, name: skillName || null }),
      })
      setMessage({ type: 'success', text: '技能安装成功' })
      setShowInstall(null)
      setGitUrl('')
      setSkillName('')
      loadSkills()
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '安装失败' })
    } finally {
      setInstalling(false)
    }
  }

  const installFromPath = async () => {
    if (!localPath.trim()) return
    setInstalling(true)
    setMessage(null)
    try {
      await api('/skills/install/path', {
        method: 'POST',
        body: JSON.stringify({ source_path: localPath, name: skillName || null }),
      })
      setMessage({ type: 'success', text: '技能导入成功' })
      setShowInstall(null)
      setLocalPath('')
      setSkillName('')
      loadSkills()
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '导入失败' })
    } finally {
      setInstalling(false)
    }
  }

  const deleteSkill = async (name: string) => {
    if (!confirm(`确定要删除技能 "${name}" 吗？`)) return
    setDeleting(name)
    setMessage(null)
    try {
      await api('/skills/delete', {
        method: 'DELETE',
        body: JSON.stringify({ name }),
      })
      setMessage({ type: 'success', text: '技能删除成功' })
      loadSkills()
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '删除失败' })
    } finally {
      setDeleting(null)
    }
  }

  const workspaceSkills = skills.filter(s => s.source === 'workspace')
  const builtinSkills = skills.filter(s => s.source === 'builtin')

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Puzzle className="w-5 h-5 text-purple-400" />
          技能
          <span className="text-sm text-[var(--text-secondary)] font-normal">({skills.length} 个)</span>
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={loadSkills}
            title="刷新"
            className="p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          {canEdit() && (
            <div className="relative">
              <button
                onClick={() => setShowInstall(showInstall ? null : 'git')}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium"
              >
                <Plus className="w-4 h-4" /> 添加技能
              </button>
            </div>
          )}
        </div>
      </div>

      {message && (
        <div className={`p-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-[var(--success)]/10 text-[var(--success)]' : 'bg-[var(--danger)]/10 text-[var(--danger)]'}`}>
          {message.text}
        </div>
      )}

      {/* Install Modal */}
      {showInstall && (
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">添加新技能</h3>
            <button onClick={() => setShowInstall(null)} title="关闭" className="p-1 rounded-lg hover:bg-[var(--bg-tertiary)]">
              <X className="w-4 h-4" />
            </button>
          </div>
          
          {/* Method Tabs */}
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setShowInstall('git')}
              className={cn(
                'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                showInstall === 'git'
                  ? 'bg-[var(--accent)] text-white'
                  : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              )}
            >
              <GitBranch className="w-4 h-4" /> Git 仓库
            </button>
            <button
              onClick={() => setShowInstall('path')}
              className={cn(
                'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                showInstall === 'path'
                  ? 'bg-[var(--accent)] text-white'
                  : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              )}
            >
              <FolderOpen className="w-4 h-4" /> 本地路径
            </button>
          </div>

          {showInstall === 'git' && (
            <div className="space-y-3">
              <div>
                <label className="text-xs text-[var(--text-secondary)] mb-1 block">Git 仓库 URL</label>
                <input
                  type="text"
                  value={gitUrl}
                  onChange={(e) => setGitUrl(e.target.value)}
                  placeholder="https://github.com/user/skill-name.git"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-[var(--text-secondary)] mb-1 block">技能名称（可选）</label>
                <input
                  type="text"
                  value={skillName}
                  onChange={(e) => setSkillName(e.target.value)}
                  placeholder="留空则使用仓库名"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-sm"
                />
              </div>
              <button
                onClick={installFromGit}
                disabled={!gitUrl.trim() || installing}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium disabled:opacity-40"
              >
                {installing ? '安装中...' : '从 Git 安装'}
              </button>
            </div>
          )}

          {showInstall === 'path' && (
            <div className="space-y-3">
              <div>
                <label className="text-xs text-[var(--text-secondary)] mb-1 block">本地路径</label>
                <input
                  type="text"
                  value={localPath}
                  onChange={(e) => setLocalPath(e.target.value)}
                  placeholder="/path/to/skill-directory"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-[var(--text-secondary)] mb-1 block">技能名称（可选）</label>
                <input
                  type="text"
                  value={skillName}
                  onChange={(e) => setSkillName(e.target.value)}
                  placeholder="留空则使用文件夹名"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-sm"
                />
              </div>
              <button
                onClick={installFromPath}
                disabled={!localPath.trim() || installing}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium disabled:opacity-40"
              >
                {installing ? '导入中...' : '从本地导入'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Workspace Skills */}
      {workspaceSkills.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-[var(--text-secondary)] mb-3 flex items-center gap-2">
            <Package className="w-4 h-4" /> 工作区技能
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {workspaceSkills.map(skill => (
              <SkillCard
                key={skill.name}
                skill={skill}
                onDelete={isAdmin() ? () => deleteSkill(skill.name) : undefined}
                deleting={deleting === skill.name}
              />
            ))}
          </div>
        </div>
      )}

      {/* Builtin Skills */}
      {builtinSkills.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-[var(--text-secondary)] mb-3 flex items-center gap-2">
            <Wrench className="w-4 h-4" /> 内置技能
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {builtinSkills.map(skill => (
              <SkillCard key={skill.name} skill={skill} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function SkillCard({ skill, onDelete, deleting }: { skill: SkillInfo; onDelete?: () => void; deleting?: boolean }) {
  return (
    <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-4 hover:border-[var(--accent)]/50 transition-all group">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <div className={cn(
            'p-1.5 rounded-lg',
            skill.source === 'workspace' ? 'bg-purple-500/10 text-purple-400' : 'bg-[var(--accent)]/10 text-[var(--accent)]'
          )}>
            <Puzzle className="w-4 h-4" />
          </div>
          <span className="font-medium text-sm">{skill.name}</span>
        </div>
        <div className="flex items-center gap-2">
          {skill.always && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--success)]/10 text-[var(--success)]">always</span>
          )}
          {skill.source === 'workspace' && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">workspace</span>
          )}
        </div>
      </div>
      <p className="text-xs text-[var(--text-secondary)] mt-2 line-clamp-2">{skill.description || '暂无描述'}</p>
      <div className="flex items-center justify-between mt-3 pt-2 border-t border-[var(--border)]">
        <span className="text-[10px] text-[var(--text-secondary)]/60 font-mono truncate max-w-[70%]">{skill.path.split('/').slice(-2).join('/')}</span>
        {onDelete && (
          <button
            onClick={onDelete}
            disabled={deleting}
            title="删除"
            className="p-1 rounded text-[var(--text-secondary)] hover:text-[var(--danger)] hover:bg-[var(--danger)]/10 opacity-0 group-hover:opacity-100 transition-all"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function SkillsPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Puzzle className="w-6 h-6 text-[var(--accent)]" />
          技能 & 工具
        </h1>
        <p className="text-[var(--text-secondary)] text-sm mt-1">管理内置工具和外置技能</p>
      </div>

      <div className="space-y-8">
        <ToolsSection />
        <SkillsSection />
      </div>
    </div>
  )
}
