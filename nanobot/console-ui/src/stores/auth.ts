import { create } from 'zustand'
import { api, setToken, clearToken } from '../api/client'

interface User {
  username: string
  role: 'admin' | 'editor' | 'viewer'
  created_at: string
}

interface AuthState {
  user: User | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
  isAdmin: () => boolean
  canEdit: () => boolean
}

export const useAuth = create<AuthState>((set, get) => ({
  user: null,
  loading: true,

  login: async (username, password) => {
    const res = await api<{ access_token: string; user: User }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    setToken(res.access_token)
    set({ user: res.user })
  },

  logout: () => {
    clearToken()
    set({ user: null })
  },

  checkAuth: async () => {
    try {
      const user = await api<User>('/auth/me')
      set({ user, loading: false })
    } catch {
      set({ user: null, loading: false })
    }
  },

  isAdmin: () => get().user?.role === 'admin',
  canEdit: () => {
    const role = get().user?.role
    return role === 'admin' || role === 'editor'
  },
}))
