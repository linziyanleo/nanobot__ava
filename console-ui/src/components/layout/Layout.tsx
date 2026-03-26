import { useRef, useEffect } from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { cn } from '../../lib/utils'
import { useResponsiveMode } from '../../hooks/useResponsiveMode'
import { navItems } from './navItems'
import Sidebar from './Sidebar'

function MobileBottomNav() {
  const location = useLocation()
  const scrollRef = useRef<HTMLDivElement>(null)
  const activeRef = useRef<HTMLAnchorElement>(null)

  // Auto-scroll to active item
  useEffect(() => {
    if (activeRef.current && scrollRef.current) {
      const container = scrollRef.current
      const el = activeRef.current
      const left = el.offsetLeft - container.offsetWidth / 2 + el.offsetWidth / 2
      container.scrollTo({ left: Math.max(0, left), behavior: 'smooth' })
    }
  }, [location.pathname])

  return (
    <nav
      ref={scrollRef}
      className="fixed bottom-0 left-0 right-0 z-30 flex items-stretch bg-[var(--bg-secondary)] border-t border-[var(--border)] overflow-x-auto scrollbar-none safe-bottom"
      style={{ WebkitOverflowScrolling: 'touch', paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      {navItems.map(item => {
        const isActive =
          item.to === '/'
            ? location.pathname === '/'
            : location.pathname.startsWith(item.to)
        return (
          <NavLink
            key={item.to}
            to={item.to}
            ref={isActive ? activeRef : undefined}
            className={cn(
              'flex flex-col items-center justify-center gap-0.5 min-w-[4rem] py-2 px-2 text-center transition-colors shrink-0',
              isActive
                ? 'text-[var(--accent)]'
                : 'text-[var(--text-secondary)]',
            )}
          >
            <item.icon className={cn('w-5 h-5', isActive && 'drop-shadow-sm')} />
            <span className={cn('text-[10px] leading-tight', isActive ? 'font-semibold' : 'font-medium')}>{item.label}</span>
          </NavLink>
        )
      })}
    </nav>
  )
}

export default function Layout() {
  const { isMobile } = useResponsiveMode()

  if (isMobile) {
    return (
      <div className="flex flex-col h-dvh">
        <main className="flex-1 min-h-0 overflow-y-auto p-4 pb-20">
          <Outlet />
        </main>
        <MobileBottomNav />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 min-w-0 p-6">
        <Outlet />
      </main>
    </div>
  )
}
