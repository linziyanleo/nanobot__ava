import { useEffect, useState } from 'react'
import { Pencil, Trash2, UserPlus, LogOut } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../stores/auth'

interface User {
  username: string
  role: string
  created_at: string
}

export default function UsersPage() {
  const { logout, isAdmin } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [showForm, setShowForm] = useState(false)
  const [editingUser, setEditingUser] = useState<string | null>(null)
  const [form, setForm] = useState({ username: '', password: '', role: 'viewer' })
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const loadUsers = async () => {
    const list = await api<User[]>('/users')
    setUsers(list)
  }

  useEffect(() => { loadUsers() }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setMessage(null)
    try {
      if (editingUser) {
        await api(`/users/${editingUser}`, {
          method: 'PUT',
          body: JSON.stringify({
            password: form.password || null,
            role: form.role,
          }),
        })
        setMessage({ type: 'success', text: 'User updated' })
      } else {
        await api('/users', {
          method: 'POST',
          body: JSON.stringify(form),
        })
        setMessage({ type: 'success', text: 'User created' })
      }
      setShowForm(false)
      setEditingUser(null)
      setForm({ username: '', password: '', role: 'viewer' })
      loadUsers()
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed' })
    }
  }

  const deleteUser = async (username: string) => {
    if (!confirm(`Delete user "${username}"?`)) return
    try {
      await api(`/users/${username}`, { method: 'DELETE' })
      loadUsers()
      setMessage({ type: 'success', text: 'User deleted' })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Delete failed' })
    }
  }

  const startEdit = (user: User) => {
    setEditingUser(user.username)
    setForm({ username: user.username, password: '', role: user.role })
    setShowForm(true)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">用户</h1>
        <div className="flex gap-2">
          {isAdmin() && (
            <button
              onClick={() => {
                setShowForm(true);
                setEditingUser(null);
                setForm({ username: '', password: '', role: 'viewer' });
              }}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium"
            >
              <UserPlus className="w-4 h-4" /> 添加用户
            </button>
          )}
          <button
            onClick={logout}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--danger)]/10 text-[var(--danger)] hover:bg-[var(--danger)]/20 text-sm font-medium"
          >
            <LogOut className="w-4 h-4" /> 退出登录
          </button>
        </div>
      </div>

      {message && (
        <div
          className={`mb-4 p-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-[var(--success)]/10 text-[var(--success)]' : 'bg-[var(--danger)]/10 text-[var(--danger)]'}`}
        >
          {message.text}
        </div>
      )}

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="mb-6 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-5 space-y-4"
        >
          <h2 className="text-lg font-semibold">{editingUser ? '编辑用户' : '新用户'}</h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">用户名</label>
              <input
                type="text"
                value={form.username}
                onChange={e => setForm({ ...form, username: e.target.value })}
                disabled={!!editingUser}
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-[var(--text-primary)] disabled:opacity-50"
                required={!editingUser}
              />
            </div>
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">
                密码 {editingUser && '(留空则不修改)'}
              </label>
              <input
                type="password"
                value={form.password}
                onChange={e => setForm({ ...form, password: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-[var(--text-primary)]"
                required={!editingUser}
              />
            </div>
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">角色</label>
              <select
                value={form.role}
                onChange={e => setForm({ ...form, role: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-[var(--text-primary)]"
              >
                <option value="admin">管理员</option>
                <option value="editor">可编辑</option>
                <option value="viewer">可查看</option>
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium">
              {editingUser ? '更新' : '创建'}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] text-sm"
            >
              取消
            </button>
          </div>
        </form>
      )}

      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[var(--border)]">
              <th className="text-left px-5 py-3 text-xs font-medium text-[var(--text-secondary)] uppercase">用户名</th>
              <th className="text-left px-5 py-3 text-xs font-medium text-[var(--text-secondary)] uppercase">角色</th>
              <th className="text-left px-5 py-3 text-xs font-medium text-[var(--text-secondary)] uppercase">
                创建时间
              </th>
              <th className="text-right px-5 py-3 text-xs font-medium text-[var(--text-secondary)] uppercase">操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr
                key={u.username}
                className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-tertiary)]/50"
              >
                <td className="px-5 py-3 text-sm font-medium">{u.username}</td>
                <td className="px-5 py-3 text-sm">
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      u.role === 'admin'
                        ? 'bg-[var(--danger)]/10 text-[var(--danger)]'
                        : u.role === 'editor'
                          ? 'bg-[var(--accent)]/10 text-[var(--accent)]'
                          : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]'
                    }`}
                  >
                    {u.role}
                  </span>
                </td>
                <td className="px-5 py-3 text-sm text-[var(--text-secondary)]">
                  {u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}
                </td>
                <td className="px-5 py-3 text-right">
                  <div className="flex gap-1 justify-end">
                    <button
                      onClick={() => startEdit(u)}
                      className="p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-[var(--accent)] hover:bg-[var(--bg-tertiary)]"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => deleteUser(u.username)}
                      className="p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-[var(--danger)] hover:bg-[var(--bg-tertiary)]"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
