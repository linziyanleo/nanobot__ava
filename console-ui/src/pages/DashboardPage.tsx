import { useEffect, useState, useCallback } from 'react'
import {
  Server,
  Settings,
  Brain,
  UserCog,
  MessageSquare,
  Activity,
  RefreshCw,
  Power,
  AlertTriangle,
  Cpu,
  Loader2,
  Clock,
  ChevronRight,
  Hammer,
  Shield,
  ArrowUpCircle,
  X,
} from 'lucide-react';
import { api } from '../api/client'
import { useAuth } from '../stores/auth'
import { useNavigate } from 'react-router-dom'
import { useResponsiveMode } from '../hooks/useResponsiveMode'
import { useVersionCheck } from '../hooks/useVersionCheck'

interface GatewayStatusData {
  running: boolean
  pid: number | null
  uptime_seconds: number | null
  gateway_port: number | null
  console_port: number | null
  supervised: boolean
  supervisor: string | null
  restart_pending: boolean
  boot_generation: number
  last_exit_reason: string | null
}

interface ActiveTask {
  task_id: string;
  task_type: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  prompt_preview: string;
  started_at: number | null;
  elapsed_ms: number;
}

interface ActiveTasksResponse {
  running: number;
  total: number;
  tasks: ActiveTask[];
}

export default function DashboardPage() {
  const [status, setStatus] = useState<GatewayStatusData | null>(null)
  const [restarting, setRestarting] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [gwMessage, setGwMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const { user, isAdmin } = useAuth();
  const navigate = useNavigate()
  const { isMobile } = useResponsiveMode()
  const { currentVersion, updateAvailable, dismiss, refresh } = useVersionCheck()

  const [activeTasks, setActiveTasks] = useState<ActiveTasksResponse | null>(null);

  const loadStatus = useCallback(() => {
    api<GatewayStatusData>('/gateway/status').then(setStatus).catch(() => {})
  }, [])

  const loadActiveTasks = useCallback(() => {
    api<ActiveTasksResponse>('/bg-tasks?include_finished=false')
      .then(setActiveTasks)
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadStatus();
    loadActiveTasks();
    const interval = setInterval(loadStatus, 10000);
    const taskInterval = setInterval(loadActiveTasks, 3000);
    return () => {
      clearInterval(interval);
      clearInterval(taskInterval);
    };
  }, [loadStatus, loadActiveTasks]);

  useEffect(() => {
    if (activeTasks && activeTasks.running > 0) {
      const timer = setInterval(() => setActiveTasks(d => (d ? { ...d } : d)), 1000);
      return () => clearInterval(timer);
    }
  }, [activeTasks?.running]);

  useEffect(() => {
    if (countdown <= 0) return;
    const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
    return () => clearTimeout(timer);
  }, [countdown]);

  const handleRestart = async (force: boolean = false) => {
    if (!confirm(`重启网关${force ? ' (强制)' : ''}? 控制台将短暂断开连接。`)) return;
    setRestarting(true);
    setGwMessage(null);
    try {
      const delayMs = 5000;
      await api('/gateway/restart', {
        method: 'POST',
        body: JSON.stringify({ delay_ms: delayMs, force }),
      });
      setCountdown(Math.ceil(delayMs / 1000) + 5);
      setGwMessage({ type: 'success', text: `网关重启将在 ${delayMs / 1000}s 后执行` });
    } catch (err: unknown) {
      setGwMessage({ type: 'error', text: err instanceof Error ? err.message : '重启失败' });
    } finally {
      setRestarting(false);
    }
  };

  const handleRebuild = async () => {
    if (!confirm('重建前端？不会影响后端进程和连接。')) return;
    setRebuilding(true);
    setGwMessage(null);
    try {
      const res = await api<{ success: boolean; duration_ms: number; version_hash: string; error: string }>('/gateway/console/rebuild', {
        method: 'POST',
      });
      if (res.success) {
        setGwMessage({ type: 'success', text: `前端重建完成 (${res.duration_ms}ms)，刷新页面即可加载新版本` });
      } else {
        setGwMessage({ type: 'error', text: `重建失败: ${res.error}` });
      }
    } catch (err: unknown) {
      setGwMessage({ type: 'error', text: err instanceof Error ? err.message : '重建失败' });
    } finally {
      setRebuilding(false);
    }
  };

  const formatUptime = (s: number | null) => {
    if (s == null) return 'N/A';
    const d = Math.floor(s / 86400);
    const h = Math.floor((s % 86400) / 3600);
    const m = Math.floor((s % 3600) / 60);
    const parts: string[] = [];
    if (d > 0) parts.push(`${d}天`);
    if (h > 0) parts.push(`${h}小时`);
    parts.push(`${m}分钟`);
    return parts.join(' ');
  };

  const shortUptime = (s: number | null) => {
    if (s == null) return 'N/A';
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  };

  const cards = [
    {
      icon: Settings,
      label: 'Config.json',
      value: '配置',
      sub: '编辑配置',
      color: 'text-[var(--accent)]',
      onClick: () => navigate('/config'),
    },
    {
      icon: Brain,
      label: 'MEMORY.md',
      value: '记忆',
      sub: '全局记忆 & 个人记忆',
      color: 'text-[var(--warning)]',
      onClick: () => navigate('/memory'),
    },
    {
      icon: UserCog,
      label: 'SOUL.md',
      value: '人设',
      sub: 'Agent 核心配置文件',
      color: 'text-green-400',
      onClick: () => navigate('/persona'),
    },
    {
      icon: MessageSquare,
      label: 'Sessions',
      value: '聊天',
      sub: '测试 Agent 对话',
      color: 'text-purple-400',
      onClick: () => navigate('/chat'),
    },
  ];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">控制台</h1>
        <p className="text-[var(--text-secondary)] text-sm mt-1">欢迎回来, {user?.username}</p>
      </div>

      {isMobile ? (
        <div className="grid grid-cols-4 gap-2 mb-4">
          {cards.map(card => (
            <button
              key={card.label}
              onClick={card.onClick}
              className="flex flex-col items-center gap-1.5 py-3 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl hover:border-[var(--accent)]/50 transition-all"
            >
              <div className={`p-2 rounded-lg bg-[var(--bg-tertiary)] ${card.color}`}>
                <card.icon className="w-4 h-4" />
              </div>
              <span className="text-xs font-medium">{card.value}</span>
            </button>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
          {cards.map(card => (
            <button
              key={card.label}
              onClick={card.onClick}
              className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-5 text-left hover:border-[var(--accent)]/50 transition-all group"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className={`p-2 rounded-lg bg-[var(--bg-tertiary)] ${card.color}`}>
                  <card.icon className="w-5 h-5" />
                </div>
                <span className="text-sm text-[var(--text-secondary)]">{card.label}</span>
              </div>
              <p className={`text-xl font-semibold ${card.color}`}>{card.value}</p>
              {card.sub && <p className="text-xs text-[var(--text-secondary)] mt-1">{card.sub}</p>}
            </button>
          ))}
        </div>
      )}

      {/* Version update banner */}
      {updateAvailable && (
        <div className="mb-4 p-3 rounded-xl bg-[var(--accent)]/10 border border-[var(--accent)]/20 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ArrowUpCircle className="w-4 h-4 text-[var(--accent)]" />
            <span className="text-sm text-[var(--accent)] font-medium">前端新版本可用</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={refresh}
              className="px-3 py-1 rounded-lg bg-[var(--accent)] text-white text-xs font-medium hover:bg-[var(--accent)]/80"
            >
              刷新加载
            </button>
            <button onClick={dismiss} className="p-1 rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Gateway Section */}
      {gwMessage && (
        <div
          className={`mb-4 p-3 rounded-lg text-sm ${gwMessage.type === 'success' ? 'bg-[var(--success)]/10 text-[var(--success)]' : 'bg-[var(--danger)]/10 text-[var(--danger)]'}`}
        >
          {gwMessage.text}
        </div>
      )}

      {countdown > 0 && (
        <div className="mb-4 p-4 rounded-xl bg-[var(--warning)]/10 border border-[var(--warning)]/20 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-[var(--warning)]" />
          <div>
            <p className="text-sm font-medium text-[var(--warning)]">网关重启中</p>
            <p className="text-xs text-[var(--text-secondary)]">预计将在 ~{countdown}s 后恢复。页面将自动重新连接。</p>
          </div>
        </div>
      )}

      <div
        className={`bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl ${isMobile ? 'p-3' : 'p-5'} mb-6`}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={`p-2 rounded-lg ${status?.running ? 'bg-[var(--success)]/10' : 'bg-[var(--danger)]/10'}`}>
              <Server className={`w-5 h-5 ${status?.running ? 'text-[var(--success)]' : 'text-[var(--danger)]'}`} />
            </div>
            <div>
              <h2 className="text-sm font-semibold flex items-center gap-1.5">
                {status?.running ? '网关运行中' : '网关未运行'}
                <button
                  onClick={loadStatus}
                  className="p-1 rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors"
                  title="刷新状态"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </h2>
              <p className="text-[10px] text-[var(--text-secondary)]">
                {status?.running
                  ? `PID: ${status.pid} · ${shortUptime(status.uptime_seconds)} · 端口: ${status.gateway_port}`
                  : '未检测到'}
              </p>
            </div>
          </div>
          {isAdmin() && (
            <div className="flex gap-1.5">
              <button
                onClick={handleRebuild}
                disabled={rebuilding}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent)]/80 text-white text-[11px] font-medium disabled:opacity-50"
              >
                {rebuilding ? <Loader2 className="w-3 h-3 animate-spin" /> : <Hammer className="w-3 h-3" />}
                {isMobile ? '' : rebuilding ? 'Building...' : 'Rebuild UI'}
              </button>
              <button
                onClick={() => handleRestart(false)}
                disabled={restarting}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[var(--warning)] hover:bg-[var(--warning)]/80 text-black text-[11px] font-medium disabled:opacity-50"
              >
                <RefreshCw className="w-3 h-3" />
                {isMobile ? '' : restarting ? 'Scheduling...' : 'Restart'}
              </button>
              <button
                onClick={() => handleRestart(true)}
                disabled={restarting}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[var(--danger)] hover:bg-[var(--danger)]/80 text-white text-[11px] font-medium disabled:opacity-50"
              >
                <Power className="w-3 h-3" />
                {isMobile ? '' : 'Force'}
              </button>
            </div>
          )}
        </div>

        {!isMobile && (
          <div className="grid grid-cols-4 gap-3 mb-3">
            <div className="bg-[var(--bg-primary)] rounded-lg p-3">
              <p className="text-[10px] text-[var(--text-secondary)] mb-0.5">状态</p>
              <p
                className={`text-sm font-semibold ${status?.running ? 'text-[var(--success)]' : 'text-[var(--danger)]'}`}
              >
                {status?.running ? '在线' : '离线'}
              </p>
            </div>
            <div className="bg-[var(--bg-primary)] rounded-lg p-3">
              <p className="text-[10px] text-[var(--text-secondary)] mb-0.5">PID</p>
              <p className="text-sm font-semibold">{status?.pid ?? '-'}</p>
            </div>
            <div className="bg-[var(--bg-primary)] rounded-lg p-3">
              <p className="text-[10px] text-[var(--text-secondary)] mb-0.5">端口</p>
              <p className="text-sm font-semibold">{status?.gateway_port ?? '-'}</p>
            </div>
            <div className="bg-[var(--bg-primary)] rounded-lg p-3">
              <p className="text-[10px] text-[var(--text-secondary)] mb-0.5">运行时间</p>
              <p className="text-sm font-semibold">{formatUptime(status?.uptime_seconds ?? null)}</p>
            </div>
          </div>
        )}

        {!isMobile && status && (
          <div className="grid grid-cols-4 gap-3">
            <div className="bg-[var(--bg-primary)] rounded-lg p-3">
              <p className="text-[10px] text-[var(--text-secondary)] mb-0.5">Supervisor</p>
              <p className="text-sm font-semibold flex items-center gap-1">
                <Shield className={`w-3 h-3 ${status.supervised ? 'text-[var(--success)]' : 'text-[var(--text-secondary)]'}`} />
                {status.supervised ? (status.supervisor ?? 'yes') : 'none'}
              </p>
            </div>
            <div className="bg-[var(--bg-primary)] rounded-lg p-3">
              <p className="text-[10px] text-[var(--text-secondary)] mb-0.5">Boot Generation</p>
              <p className="text-sm font-semibold">#{status.boot_generation}</p>
            </div>
            <div className="bg-[var(--bg-primary)] rounded-lg p-3">
              <p className="text-[10px] text-[var(--text-secondary)] mb-0.5">前端版本</p>
              <p className="text-sm font-semibold font-mono">{currentVersion?.hash?.slice(0, 8) ?? '-'}</p>
            </div>
            <div className="bg-[var(--bg-primary)] rounded-lg p-3">
              <p className="text-[10px] text-[var(--text-secondary)] mb-0.5">重启状态</p>
              <p className={`text-sm font-semibold ${status.restart_pending ? 'text-[var(--warning)]' : 'text-[var(--text-secondary)]'}`}>
                {status.restart_pending ? '等待重启' : '正常'}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Active Background Tasks */}
      {activeTasks && activeTasks.running > 0 && (
        <div className="bg-[var(--bg-secondary)] border border-blue-500/30 rounded-xl p-5 mb-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-blue-500/10">
                <Cpu className="w-4 h-4 text-blue-400" />
              </div>
              <h2 className="text-sm font-semibold">后台任务</h2>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400">
                <Loader2 className="w-3 h-3 animate-spin" />
                {activeTasks.running} 运行中
              </span>
            </div>
            <button
              onClick={() => navigate('/bg-tasks')}
              className="flex items-center gap-1 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              查看全部 <ChevronRight className="w-3 h-3" />
            </button>
          </div>
          <div className="space-y-2">
            {activeTasks.tasks
              .filter(t => t.status === 'queued' || t.status === 'running')
              .slice(0, 3)
              .map(task => {
                const elapsed = task.started_at ? Math.floor(Date.now() / 1000 - task.started_at) : 0;
                const elapsedStr = elapsed >= 60 ? `${Math.floor(elapsed / 60)}m ${elapsed % 60}s` : `${elapsed}s`;
                const StatusIcon = task.status === 'running' ? Loader2 : Clock;
                return (
                  <div
                    key={task.task_id}
                    onClick={() => navigate('/bg-tasks')}
                    className="flex items-center gap-3 p-3 rounded-lg bg-[var(--bg-primary)] cursor-pointer hover:bg-[var(--bg-tertiary)] transition-colors"
                  >
                    <StatusIcon
                      className={`w-4 h-4 ${task.status === 'running' ? 'text-blue-400 animate-spin' : 'text-yellow-500'}`}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm truncate">{task.prompt_preview || '(no prompt)'}</p>
                      <p className="text-xs text-[var(--text-secondary)]">
                        {task.task_type} · {task.task_id} · {elapsedStr}
                      </p>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-3">
          <Activity className="w-4 h-4 text-[var(--accent)]" />
          <h2 className="text-sm font-semibold">快速信息</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-[var(--text-secondary)]">角色</p>
            <p className="font-medium capitalize">{user?.role}</p>
          </div>
          <div>
            <p className="text-[var(--text-secondary)]">网关端口</p>
            <p className="font-medium">{status?.gateway_port ?? '—'}</p>
          </div>
          <div>
            <p className="text-[var(--text-secondary)]">控制台端口</p>
            <p className="font-medium">{status?.console_port ?? '—'}</p>
          </div>
          <div>
            <p className="text-[var(--text-secondary)]">状态</p>
            <p className={`font-medium ${status?.running ? 'text-[var(--success)]' : 'text-[var(--danger)]'}`}>
              {status?.running ? '在线' : '离线'}
            </p>
          </div>
        </div>
      </div>

      <p className="text-[10px] text-[var(--text-secondary)] font-mono opacity-60 text-right mt-4">
        v{__BUILD_VERSION__} · Built{' '}
        {new Date(__BUILD_TIME__).toLocaleString('zh-CN', {
          timeZone: 'Asia/Shanghai',
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          hour12: false,
        })}
      </p>
    </div>
  );
}
