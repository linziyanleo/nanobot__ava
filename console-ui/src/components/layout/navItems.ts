import {
  LayoutDashboard,
  Settings,
  Brain,
  Image,
  UserCog,
  Puzzle,
  MessageSquare,
  BarChart3,
  Timer,
  User,
  Cpu,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react'

export interface NavItem {
  to: string
  icon: LucideIcon
  label: string
  adminOnly?: boolean
}

export const navItems: NavItem[] = [
  { to: '/', icon: LayoutDashboard, label: '控制台' },
  { to: '/config', icon: Settings, label: '配置' },
  { to: '/tasks', icon: Timer, label: '定时任务' },
  { to: '/bg-tasks', icon: Cpu, label: '后台任务' },
  { to: '/memory', icon: Brain, label: '记忆' },
  { to: '/media', icon: Image, label: '生成图片' },
  { to: '/persona', icon: UserCog, label: '人设' },
  { to: '/skills', icon: Puzzle, label: '技能 & 工具' },
  { to: '/chat', icon: MessageSquare, label: '聊天' },
  // { to: '/browser', icon: Globe, label: '浏览器' },  // 暂时隐藏，浏览器工具收拢到对话内
  { to: '/tokens', icon: BarChart3, label: 'Token 统计' },
]

export const userNavItem: NavItem = {
  to: '/users',
  icon: User,
  label: '用户',
  adminOnly: true,
}
