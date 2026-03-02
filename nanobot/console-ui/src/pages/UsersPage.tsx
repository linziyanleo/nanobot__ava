import { useEffect, useState } from 'react'
import { Pencil, Trash2, UserPlus } from 'lucide-react'
import { api } from '../api/client'

interface User {
  username: string
  role: string
  created_at: string
}

export default function UsersPage() {
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
        <h1 className="text-2xl font-bold">Users</h1>
        <button
          onClick={() => { setShowForm(true); setEditingUser(null); setForm({ username: '', password: '', role: 'viewer' }) }}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium"
        >
          <UserPlus className="w-4 h-4" /> Add User
        </button>
      </div>

      {message && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-[var(--success)]/10 text-[var(--success)]' : 'bg-[var(--danger)]/10 text-[var(--danger)]'}`}>
          {message.text}
        </div>
      )}

      {showForm && (
        <form onSubmit={handleSubmit} className="mb-6 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-5 space-y-4">
          <h2 className="text-lg font-semibold">{editingUser ? 'Edit User' : 'New User'}</h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">Username</label>
              <input
                type="text"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                disabled={!!editingUser}
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-[var(--text-primary)] disabled:opacity-50"
                required={!editingUser}
              />
            </div>
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">
                Password {editingUser && '(leave blank to keep)'}
              </label>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-[var(--text-primary)]"
                required={!editingUser}
              />
            </div>
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">Role</label>
              <select
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-[var(--text-primary)]"
              >
                <option value="admin">Admin</option>
                <option value="editor">Editor</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium">
              {editingUser ? 'Update' : 'Create'}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] text-sm">
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[var(--border)]">
              <th className="text-left px-5 py-3 text-xs font-medium text-[var(--text-secondary)] uppercase">Username</th>
              <th className="text-left px-5 py-3 text-xs font-medium text-[var(--text-secondary)] uppercase">Role</th>
              <th className="text-left px-5 py-3 text-xs font-medium text-[var(--text-secondary)] uppercase">Created</th>
              <th className="text-right px-5 py-3 text-xs font-medium text-[var(--text-secondary)] uppercase">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.username} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-tertiary)]/50">
                <td className="px-5 py-3 text-sm font-medium">{u.username}</td>
                <td className="px-5 py-3 text-sm">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    u.role === 'admin' ? 'bg-[var(--danger)]/10 text-[var(--danger)]' :
                    u.role === 'editor' ? 'bg-[var(--accent)]/10 text-[var(--accent)]' :
                    'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]'
                  }`}>
                    {u.role}
                  </span>
                </td>
                <td className="px-5 py-3 text-sm text-[var(--text-secondary)]">
                  {u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}
                </td>
                <td className="px-5 py-3 text-right">
                  <div className="flex gap-1 justify-end">
                    <button onClick={() => startEdit(u)} className="p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-[var(--accent)] hover:bg-[var(--bg-tertiary)]">
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button onClick={() => deleteUser(u.username)} className="p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-[var(--danger)] hover:bg-[var(--bg-tertiary)]">
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
  )
}
