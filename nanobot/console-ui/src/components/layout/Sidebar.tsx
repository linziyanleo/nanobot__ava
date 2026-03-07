import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Settings, FileText, MessageSquare,
  Server, BarChart3, ImageIcon, Users, ClipboardList, LogOut, Bot,
} from 'lucide-react'
import { useAuth } from '../../stores/auth'
import { cn } from '../../lib/utils'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: '控制台' },
  { to: '/config', icon: Settings, label: '配置' },
  { to: '/files', icon: FileText, label: '文件' },
  { to: '/chat', icon: MessageSquare, label: '聊天' },
  { to: '/gateway', icon: Server, label: '网关' },
  { to: '/tokens', icon: BarChart3, label: 'Token 统计' },
  { to: '/media', icon: ImageIcon, label: '媒体' },
  { to: '/users', icon: Users, label: '用户', admin: true },
  { to: '/audit', icon: ClipboardList, label: '审计', admin: true },
];

export default function Sidebar() {
  const { user, logout, isAdmin } = useAuth()

  return (
    <aside className="w-60 shrink-0 h-screen bg-[var(--bg-secondary)] border-r border-[var(--border)] flex flex-col sticky left-0 top-0 z-20">
      <div className="p-5 border-b border-[var(--border)] flex items-center gap-3">
        <Bot className="w-7 h-7 text-[var(--accent)]" />
        <div>
          <h1 className="text-base font-bold text-[var(--text-primary)]">Nanobot 控制台</h1>
          <p className="text-xs text-[var(--text-secondary)]">管理面板</p>
        </div>
      </div>

      <nav className="flex-1 py-3 px-3 space-y-0.5 overflow-y-auto">
        {navItems.map(item => {
          if (item.admin && !isAdmin()) return null;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150',
                  isActive
                    ? 'bg-[var(--accent)] text-white font-medium'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]',
                )
              }
            >
              <item.icon className="w-4.5 h-4.5" />
              {item.label}
            </NavLink>
          );
        })}
      </nav>

      <div className="p-4 border-t border-[var(--border)]">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-[var(--text-primary)]">{user?.username}</p>
            <p className="text-xs text-[var(--text-secondary)] capitalize">{user?.role}</p>
          </div>
          <button
            onClick={logout}
            className="p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--danger)] hover:bg-[var(--bg-tertiary)] transition-colors"
            title="Logout"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
