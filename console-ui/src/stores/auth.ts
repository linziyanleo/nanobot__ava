import { create } from 'zustand'
import { api } from '../api/client'

export type UserRole = 'admin' | 'editor' | 'viewer' | 'mock_tester'

export interface User {
  username: string
  role: UserRole
  created_at: string
}

interface AuthState {
  user: User | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
  isAdmin: () => boolean
  isMockTester: () => boolean
  canEdit: () => boolean
}

export const useAuth = create<AuthState>((set, get) => ({
  user: null,
  loading: true,

  login: async (username, password) => {
    const res = await api<{ user: User }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    set({ user: res.user })
  },

  logout: () => {
    void api('/auth/logout', { method: 'POST' }).catch(() => {})
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
  isMockTester: () => get().user?.role === 'mock_tester',
  canEdit: () => {
    const role = get().user?.role
    return role === 'admin' || role === 'editor' || role === 'mock_tester'
  },
}))
