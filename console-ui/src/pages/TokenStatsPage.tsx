import { useEffect, useState, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  RefreshCw,
  BarChart3,
  List,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Search,
  X,
  SlidersHorizontal,
} from 'lucide-react';
import { useResponsiveMode } from '../hooks/useResponsiveMode';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import { api } from '../api/client';
import { useAuth } from '../stores/auth';
import { cn } from '../lib/utils';

interface TokenRecord {
  timestamp: string;
  model: string;
  provider: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  session_key: string;
  user_message: string;
  output_content: string;
  system_prompt_preview: string;
  conversation_history: string;
  full_request_payload: string;
  finish_reason: string;
  model_role: string;
  cached_tokens: number;
  cache_creation_tokens: number;
  cost_usd: number;
}

interface ModelStats {
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  calls: number;
}

interface ProviderStats {
  provider: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  calls: number;
}

interface TokenSummary {
  totals: { prompt_tokens: number; completion_tokens: number; total_tokens: number; total_calls: number };
  by_model: ModelStats[];
  by_provider: ProviderStats[];
}

interface RecordsResponse {
  records: TokenRecord[];
  total: number;
}

const PIE_COLORS = ['#3b82f6', '#8b5cf6'];

function fmtTooltip(v: number | string | ReadonlyArray<number | string> | undefined): string {
  const raw = Array.isArray(v) ? v[0] : v;
  const numeric = typeof raw === 'number' ? raw : Number(raw);
  return formatTokens(Number.isFinite(numeric) ? numeric : 0);
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
}

function shortModel(model: string): string {
  const parts = model.split('/');
  return parts[parts.length - 1];
}

// Model role icons with tooltip
const MODEL_ROLE_CONFIG: Record<string, { icon: string; label: string }> = {
  default: { icon: '🤖', label: '主模型' },
  mini: { icon: '⚡', label: '轻量模型' },
  vision: { icon: '👁️', label: '视觉模型' },
  voice: { icon: '🎙️', label: '语音模型' },
  imageGen: { icon: '🎨', label: '图像生成' },
  claude_code: { icon: '💻', label: 'Claude Code' },
};

function ModelRoleIcon({ role }: { role: string }) {
  const config = MODEL_ROLE_CONFIG[role] || MODEL_ROLE_CONFIG.default;
  return (
    <span className="relative group/role cursor-help text-base">
      {config.icon}
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2 py-1 rounded bg-[var(--bg-tertiary)] border border-[var(--border)] text-[10px] text-[var(--text-primary)] whitespace-nowrap opacity-0 group-hover/role:opacity-100 transition-opacity pointer-events-none z-10 shadow-lg">
        {config.label}
      </span>
    </span>
  );
}

function formatCacheStatus(cachedTokens: number, cacheCreationTokens: number): React.ReactNode {
  if (!cachedTokens && !cacheCreationTokens) {
    return <span className="text-[var(--text-secondary)]">-</span>;
  }

  const parts: React.ReactNode[] = [];

  if (cacheCreationTokens > 0) {
    parts.push(
      <span key="write" className="text-amber-400" title={`写入缓存 ${cacheCreationTokens.toLocaleString()} tokens`}>
        ✍️ {formatTokens(cacheCreationTokens)}
      </span>
    );
  }

  if (cachedTokens > 0) {
    parts.push(
      <span key="hit" className="text-emerald-400" title={`命中缓存 ${cachedTokens.toLocaleString()} tokens`}>
        🎯 {formatTokens(cachedTokens)}
      </span>
    );
  }

  return (
    <span className="flex items-center gap-1.5 text-xs">
      {parts.map((part, i) => (
        <span key={i}>{part}</span>
      ))}
    </span>
  );
}

type TimePreset = 'all' | 'today' | '7d' | '30d' | 'custom';

function getPresetRange(preset: TimePreset): { start?: string; end?: string } {
  if (preset === 'all') return {};
  const now = new Date();
  const end = now.toISOString();
  if (preset === 'today') {
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();
    return { start, end };
  }
  if (preset === '7d') {
    const start = new Date(now.getTime() - 7 * 86400000).toISOString();
    return { start, end };
  }
  if (preset === '30d') {
    const start = new Date(now.getTime() - 30 * 86400000).toISOString();
    return { start, end };
  }
  return {};
}

type ModelRoleFilter = 'all' | 'claude_code' | 'chat' | 'mini' | 'voice' | 'vision';

const MODEL_ROLE_FILTER_OPTIONS: { value: ModelRoleFilter; label: string; icon: string }[] = [
  { value: 'all', label: '全部', icon: '📊' },
  { value: 'claude_code', label: 'Claude Code', icon: '💻' },
  { value: 'chat', label: '主模型', icon: '🤖' },
  { value: 'mini', label: 'Mini', icon: '⚡' },
  { value: 'voice', label: 'Voice', icon: '🎙️' },
  { value: 'vision', label: 'Vision', icon: '👁️' },
];

function buildFilterStr(
  sk: string,
  model: string,
  provider: string,
  turnSeq: string,
  preset: TimePreset,
  cStart: string,
  cEnd: string,
  modelRole: ModelRoleFilter,
): string {
  const params = new URLSearchParams();
  if (sk) params.set('session_key', sk);
  if (model) params.set('model', model);
  if (provider) params.set('provider', provider);
  if (turnSeq) params.set('turn_seq', turnSeq);
  if (modelRole && modelRole !== 'all') params.set('model_role', modelRole);
  if (preset === 'custom') {
    if (cStart) params.set('start_time', new Date(cStart).toISOString());
    if (cEnd) params.set('end_time', new Date(cEnd + 'T23:59:59').toISOString());
  } else {
    const { start, end } = getPresetRange(preset);
    if (start) params.set('start_time', start);
    if (end) params.set('end_time', end);
  }
  return params.toString();
}

export default function TokenStatsPage() {
  const { isMobile } = useResponsiveMode();
  const [searchParams, setSearchParams] = useSearchParams();
  const [view, setView] = useState<'records' | 'charts'>('records');
  const [summary, setSummary] = useState<TokenSummary | null>(null);
  const [records, setRecords] = useState<TokenRecord[]>([]);
  const [filtersExpanded, setFiltersExpanded] = useState(!isMobile);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  useAuth();
  const pageSize = 50;

  const [filterSessionKey, setFilterSessionKey] = useState(searchParams.get('session_key') || '');
  const [filterModel, setFilterModel] = useState(searchParams.get('model') || '');
  const [filterProvider, setFilterProvider] = useState(searchParams.get('provider') || '');
  const [filterTurnSeq, setFilterTurnSeq] = useState(searchParams.get('turn_seq') || '');
  const [filterModelRole, setFilterModelRole] = useState<ModelRoleFilter>('all');
  const [timePreset, setTimePreset] = useState<TimePreset>('all');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');

  const filtersRef = useRef({
    filterSessionKey,
    filterModel,
    filterProvider,
    filterTurnSeq,
    filterModelRole,
    timePreset,
    customStart,
    customEnd,
  });
  useEffect(() => {
    filtersRef.current = {
      filterSessionKey,
      filterModel,
      filterProvider,
      filterTurnSeq,
      filterModelRole,
      timePreset,
      customStart,
      customEnd,
    };
  }, [
    filterSessionKey,
    filterModel,
    filterProvider,
    filterTurnSeq,
    filterModelRole,
    timePreset,
    customStart,
    customEnd,
  ]);

  const loadSummary = useCallback(async () => {
    try {
      const s = await api<TokenSummary>('/stats/tokens');
      setSummary(s);
    } catch {
      /* ignore */
    }
  }, []);

  const loadRecords = useCallback(async (p: number = 0) => {
    setLoading(true);
    try {
      const f = filtersRef.current;
      const filterStr = buildFilterStr(
        f.filterSessionKey,
        f.filterModel,
        f.filterProvider,
        f.filterTurnSeq,
        f.timePreset,
        f.customStart,
        f.customEnd,
        f.filterModelRole,
      );
      const sep = filterStr ? '&' : '';
      const r = await api<RecordsResponse>(
        `/stats/tokens/records?limit=${pageSize}&offset=${p * pageSize}${sep}${filterStr}`,
      );
      setRecords(r.records);
      setTotal(r.total);
      setPage(p);
    } catch {
      /* ignore */
    }
    setLoading(false);
  }, []);

  // Initial load
  useEffect(() => {
    queueMicrotask(() => {
      void loadSummary();
      void loadRecords(0);
    });
  }, [loadSummary, loadRecords]);

  // When URL params change (navigation from other page), sync state and reload
  const mountedRef = useRef(false);
  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      return;
    }
    const sk = searchParams.get('session_key') || '';
    const m = searchParams.get('model') || '';
    const p = searchParams.get('provider') || '';
    const ts = searchParams.get('turn_seq') || '';
    queueMicrotask(() => {
      setFilterSessionKey(sk);
      setFilterModel(m);
      setFilterProvider(p);
      setFilterTurnSeq(ts);
      filtersRef.current = {
        ...filtersRef.current,
        filterSessionKey: sk,
        filterModel: m,
        filterProvider: p,
        filterTurnSeq: ts,
      };
      void loadRecords(0);
    });
  }, [searchParams, loadRecords]);

  const handleSearch = () => {
    const newParams: Record<string, string> = {};
    if (filterSessionKey) newParams.session_key = filterSessionKey;
    if (filterModel) newParams.model = filterModel;
    if (filterProvider) newParams.provider = filterProvider;
    if (filterTurnSeq) newParams.turn_seq = filterTurnSeq;
    setSearchParams(newParams, { replace: true });
    loadRecords(0);
  };

  const handleClearFilters = () => {
    setFilterSessionKey('');
    setFilterModel('');
    setFilterProvider('');
    setFilterTurnSeq('');
    setFilterModelRole('all');
    setTimePreset('all');
    setCustomStart('');
    setCustomEnd('');
    setSearchParams({}, { replace: true });
    filtersRef.current = {
      filterSessionKey: '',
      filterModel: '',
      filterProvider: '',
      filterTurnSeq: '',
      filterModelRole: 'all',
      timePreset: 'all',
      customStart: '',
      customEnd: '',
    };
    loadRecords(0);
  };

  const hasFilters =
    filterSessionKey ||
    filterModel ||
    filterProvider ||
    filterTurnSeq ||
    filterModelRole !== 'all' ||
    timePreset !== 'all';

  const totalPages = Math.ceil(total / pageSize);

  const pieData = summary
    ? [
        { name: 'Prompt', value: summary.totals.prompt_tokens },
        { name: 'Completion', value: summary.totals.completion_tokens },
      ]
    : [];

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {!isMobile && <h1 className="text-2xl font-bold">Token 统计</h1>}
          <div className="flex bg-[var(--bg-tertiary)] rounded-lg p-0.5">
            <button
              onClick={() => setView('records')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                view === 'records'
                  ? 'bg-[var(--accent)] text-white'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`}
            >
              <List className="w-3.5 h-3.5" />
              {!isMobile && ' 明细'}
            </button>
            <button
              onClick={() => {
                setView('charts');
                loadSummary();
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                view === 'charts'
                  ? 'bg-[var(--accent)] text-white'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              {!isMobile && ' 聚合'}
            </button>
          </div>
        </div>
        <div className="flex gap-1.5">
          <button
            onClick={() => {
              loadSummary();
              loadRecords(page);
            }}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-sm"
            title="刷新"
          >
            <RefreshCw className="w-4 h-4" />
            {!isMobile && ' 刷新'}
          </button>
        </div>
      </div>

      {/* Overview Cards */}
      {summary &&
        (isMobile ? (
          <div className="flex items-center gap-3 mb-3 px-1 text-xs overflow-x-auto">
            <span className="shrink-0">
              <span className="text-[var(--text-secondary)]">Total:</span>{' '}
              <span className="font-semibold text-[var(--accent)]">{formatTokens(summary.totals.total_tokens)}</span>
            </span>
            <span className="text-[var(--border)]">|</span>
            <span className="shrink-0">
              <span className="text-[var(--text-secondary)]">Calls:</span>{' '}
              <span className="font-semibold text-purple-400">{summary.totals.total_calls}</span>
            </span>
            <span className="text-[var(--border)]">|</span>
            <span className="shrink-0">
              <span className="text-[var(--text-secondary)]">In:</span>{' '}
              <span className="font-semibold text-cyan-400">{formatTokens(summary.totals.prompt_tokens)}</span>
            </span>
            <span className="text-[var(--border)]">|</span>
            <span className="shrink-0">
              <span className="text-[var(--text-secondary)]">Out:</span>{' '}
              <span className="font-semibold text-emerald-400">{formatTokens(summary.totals.completion_tokens)}</span>
            </span>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-4">
              <p className="text-xs text-[var(--text-secondary)] mb-1">总 Token</p>
              <p className="text-xl font-bold text-[var(--accent)]">{formatTokens(summary.totals.total_tokens)}</p>
            </div>
            <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-4">
              <p className="text-xs text-[var(--text-secondary)] mb-1">LLM 调用</p>
              <p className="text-xl font-bold text-purple-400">{summary.totals.total_calls}</p>
            </div>
            <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-4">
              <p className="text-xs text-[var(--text-secondary)] mb-1">Prompt Tokens</p>
              <p className="text-xl font-bold text-cyan-400">{formatTokens(summary.totals.prompt_tokens)}</p>
            </div>
            <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-4">
              <p className="text-xs text-[var(--text-secondary)] mb-1">Completion Tokens</p>
              <p className="text-xl font-bold text-emerald-400">{formatTokens(summary.totals.completion_tokens)}</p>
            </div>
          </div>
        ))}

      {/* Search / Filter Bar */}
      {view === 'records' && (
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-4 mb-4">
          {/* Primary filters: 功能角色 / 时间范围 / 模型 */}
          <div className="flex flex-wrap gap-1 items-end">
            <div>
              <label className="text-[10px] text-[var(--text-secondary)] mb-1 block">功能角色</label>
              <div className="flex bg-[var(--bg-primary)] rounded-lg border border-[var(--border)] p-0.5">
                {MODEL_ROLE_FILTER_OPTIONS.map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => {
                      setFilterModelRole(opt.value);
                      filtersRef.current = { ...filtersRef.current, filterModelRole: opt.value };
                      loadRecords(0);
                    }}
                    title={opt.label}
                    className={`px-1.5 py-1 rounded-md text-[10px] font-medium transition-colors flex items-center gap-0.5 ${
                      filterModelRole === opt.value
                        ? 'bg-[var(--accent)] text-white'
                        : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                    }`}
                  >
                    <span>{opt.icon}</span>
                    {opt.value === 'all' && <span>全部</span>}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-[10px] text-[var(--text-secondary)] mb-1 block">时间范围</label>
              <div className="flex bg-[var(--bg-primary)] rounded-lg border border-[var(--border)] p-0.5">
                {(['all', 'today', '7d', '30d', 'custom'] as TimePreset[]).map(p => (
                  <button
                    key={p}
                    onClick={() => {
                      setTimePreset(p);
                      if (p !== 'custom') {
                        filtersRef.current = { ...filtersRef.current, timePreset: p };
                        loadRecords(0);
                      }
                    }}
                    className={`px-1 py-1 rounded-md text-[10px] font-medium transition-colors ${
                      timePreset === p
                        ? 'bg-[var(--accent)] text-white'
                        : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                    }`}
                  >
                    {p === 'all'
                      ? '全部'
                      : p === 'today'
                        ? '今天'
                        : p === '7d'
                          ? '7天'
                          : p === '30d'
                            ? '30天'
                            : '自定义'}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex-1 min-w-[100px]">
              <label className="text-[10px] text-[var(--text-secondary)] mb-1 block">模型</label>
              <input
                type="text"
                value={filterModel}
                onChange={e => setFilterModel(e.target.value)}
                placeholder="claude-sonnet"
                className="w-full px-2.5 py-1.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/50 focus:border-[var(--accent)] outline-none"
              />
            </div>
            <div className="flex gap-1.5">
              <button
                onClick={handleSearch}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[var(--accent)] text-white text-xs font-medium hover:opacity-90"
              >
                <Search className="w-3 h-3" />
              </button>
              <button
                onClick={handleClearFilters}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] text-xs hover:text-[var(--text-primary)] ${
                  hasFilters ? 'visible' : 'invisible'
                }`}
              >
                <X className="w-3 h-3" />
              </button>
              <button
                onClick={() => setFiltersExpanded(!filtersExpanded)}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] text-xs hover:text-[var(--text-primary)]"
                title="更多筛选"
              >
                <SlidersHorizontal className="w-3 h-3" />
              </button>
            </div>
          </div>

          {/* Extended filters (collapsible) */}
          {filtersExpanded && (
            <div className="flex flex-wrap gap-1 items-end mt-2 pt-2 border-t border-[var(--border)]">
              <div className="flex-1 min-w-[120px]">
                <label className="text-[10px] text-[var(--text-secondary)] mb-1 block">Session ID</label>
                <input
                  type="text"
                  value={filterSessionKey}
                  onChange={e => setFilterSessionKey(e.target.value)}
                  placeholder="telegram:12345"
                  className="w-full px-2.5 py-1.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/50 focus:border-[var(--accent)] outline-none"
                />
              </div>
              <div className="flex-1 min-w-[80px]">
                <label className="text-[10px] text-[var(--text-secondary)] mb-1 block">Provider</label>
                <input
                  type="text"
                  value={filterProvider}
                  onChange={e => setFilterProvider(e.target.value)}
                  placeholder="yunwu"
                  className="w-full px-2.5 py-1.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/50 focus:border-[var(--accent)] outline-none"
                />
              </div>
              <div className="w-[70px]">
                <label className="text-[10px] text-[var(--text-secondary)] mb-1 block">Turn</label>
                <input
                  type="text"
                  value={filterTurnSeq}
                  onChange={e => setFilterTurnSeq(e.target.value)}
                  placeholder="0"
                  className="w-full px-2.5 py-1.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/50 focus:border-[var(--accent)] outline-none"
                />
              </div>
              {timePreset === 'custom' && (
                <>
                  <div>
                    <label className="text-[10px] text-[var(--text-secondary)] mb-1 block">开始日期</label>
                    <input
                      type="date"
                      value={customStart}
                      onChange={e => setCustomStart(e.target.value)}
                      className="px-2.5 py-1.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-xs text-[var(--text-primary)] focus:border-[var(--accent)] outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-[var(--text-secondary)] mb-1 block">结束日期</label>
                    <input
                      type="date"
                      value={customEnd}
                      onChange={e => setCustomEnd(e.target.value)}
                      className="px-2.5 py-1.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-xs text-[var(--text-primary)] focus:border-[var(--accent)] outline-none"
                    />
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {view === 'records' ? (
        /* ============ Records View ============ */
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm table-fixed">
              <colgroup>
                <col className="w-[120px]" />
                <col className="min-w-[160px]" />
                <col className="w-[60px]" />
                <col className="w-[100px]" />
                <col className="w-[85px]" />
                <col className="w-[90px]" />
                <col className="w-[120px]" />
                <col className="w-[100px]" />
                <col className="w-[80px]" />
                <col className="w-[85px]" />
                <col className="w-[50px]" />
              </colgroup>
              <thead>
                <tr className="border-b border-[var(--border)] text-[var(--text-secondary)] text-xs">
                  <th className="text-left px-4 py-3 font-medium">时间</th>
                  <th className="text-left px-4 py-3 font-medium">模型</th>
                  <th className="text-left px-4 py-3 font-medium">功能</th>
                  <th className="text-left px-4 py-3 font-medium">提供者</th>
                  <th className="text-right px-4 py-3 font-medium">Prompt</th>
                  <th className="text-right px-4 py-3 font-medium">Completion</th>
                  <th className="text-center px-4 py-3 font-medium">缓存</th>
                  <th className="text-center px-4 py-3 font-medium">类型</th>
                  <th className="text-right px-4 py-3 font-medium">Total</th>
                  <th className="text-right px-4 py-3 font-medium">Cost</th>
                  <th className="text-center px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={11} className="text-center py-8 text-[var(--text-secondary)]">
                      加载中...
                    </td>
                  </tr>
                ) : records.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="text-center py-8 text-[var(--text-secondary)]">
                      暂无数据
                    </td>
                  </tr>
                ) : (
                  records.map((r, i) => (
                    <RecordRow
                      key={`${r.timestamp}-${i}`}
                      record={r}
                      expanded={expandedRow === i}
                      onToggle={() => setExpandedRow(expandedRow === i ? null : i)}
                    />
                  ))
                )}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--border)]">
              <span className="text-xs text-[var(--text-secondary)]">
                共 {total} 条 · 第 {page + 1}/{totalPages} 页
              </span>
              <div className="flex items-center gap-1">
                <button
                  disabled={page === 0}
                  onClick={() => loadRecords(page - 1)}
                  className="px-2.5 py-1 rounded text-xs bg-[var(--bg-tertiary)] text-[var(--text-secondary)] disabled:opacity-30 hover:text-[var(--text-primary)]"
                >
                  &lsaquo;
                </button>
                <PageNumbers current={page} total={totalPages} onPage={loadRecords} />
                <button
                  disabled={page >= totalPages - 1}
                  onClick={() => loadRecords(page + 1)}
                  className="px-2.5 py-1 rounded text-xs bg-[var(--bg-tertiary)] text-[var(--text-secondary)] disabled:opacity-30 hover:text-[var(--text-primary)]"
                >
                  &rsaquo;
                </button>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* ============ Charts View ============ */
        <div className="space-y-6">
          {/* By Model */}
          {summary && summary.by_model.length > 0 && (
            <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-5">
              <h2 className="text-sm font-semibold mb-4">按模型统计</h2>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={summary.by_model.map(m => ({ ...m, label: shortModel(m.model) }))}
                    layout="vertical"
                    margin={{ left: 10 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis
                      type="number"
                      tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                      tickFormatter={formatTokens}
                    />
                    <YAxis
                      type="category"
                      dataKey="label"
                      width={140}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--bg-tertiary)',
                        border: '1px solid var(--border)',
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      labelStyle={{ color: 'var(--text-primary)' }}
                      formatter={fmtTooltip}
                    />
                    <Bar dataKey="prompt_tokens" name="Prompt" fill="#3b82f6" stackId="a" radius={[0, 0, 0, 0]} />
                    <Bar
                      dataKey="completion_tokens"
                      name="Completion"
                      fill="#8b5cf6"
                      stackId="a"
                      radius={[0, 4, 4, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* By Provider */}
            {summary && summary.by_provider.length > 0 && (
              <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-5">
                <h2 className="text-sm font-semibold mb-4">按 Provider 统计</h2>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={summary.by_provider}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="provider" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                      <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={formatTokens} />
                      <Tooltip
                        contentStyle={{
                          background: 'var(--bg-tertiary)',
                          border: '1px solid var(--border)',
                          borderRadius: 8,
                          fontSize: 12,
                        }}
                        formatter={fmtTooltip}
                      />
                      <Bar dataKey="prompt_tokens" name="Prompt" fill="#06b6d4" />
                      <Bar dataKey="completion_tokens" name="Completion" fill="#10b981" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Pie Chart */}
            {summary && summary.totals.total_tokens > 0 && (
              <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-5">
                <h2 className="text-sm font-semibold mb-4">Prompt / Completion 占比</h2>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={90}
                        dataKey="value"
                        label={({ name, percent }: { name?: string; percent?: number }) =>
                          `${name ?? ''} ${((percent ?? 0) * 100).toFixed(0)}%`
                        }
                      >
                        {pieData.map((_, idx) => (
                          <Cell key={idx} fill={PIE_COLORS[idx]} />
                        ))}
                      </Pie>
                      <Legend wrapperStyle={{ fontSize: 12, color: 'var(--text-secondary)' }} />
                      <Tooltip
                        contentStyle={{
                          background: 'var(--bg-tertiary)',
                          border: '1px solid var(--border)',
                          borderRadius: 8,
                          fontSize: 12,
                        }}
                        formatter={fmtTooltip}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>

          {/* Calls per model table */}
          {summary && summary.by_model.length > 0 && (
            <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-[var(--text-secondary)] text-xs">
                    <th className="text-left px-4 py-3 font-medium">模型</th>
                    <th className="text-right px-4 py-3 font-medium">调用次数</th>
                    <th className="text-right px-4 py-3 font-medium">Prompt</th>
                    <th className="text-right px-4 py-3 font-medium">Completion</th>
                    <th className="text-right px-4 py-3 font-medium">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.by_model.map(m => (
                    <tr key={m.model} className="border-b border-[var(--border)]/50 hover:bg-[var(--bg-tertiary)]/30">
                      <td className="px-4 py-2.5 font-mono text-xs">{m.model}</td>
                      <td className="px-4 py-2.5 text-right text-[var(--text-secondary)]">{m.calls}</td>
                      <td className="px-4 py-2.5 text-right">{formatTokens(m.prompt_tokens)}</td>
                      <td className="px-4 py-2.5 text-right">{formatTokens(m.completion_tokens)}</td>
                      <td className="px-4 py-2.5 text-right font-medium">{formatTokens(m.total_tokens)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CopyablePre({ children, className }: { children: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  const preRef = useRef<HTMLPreElement>(null);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const text = preRef.current?.textContent ?? children;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="relative group/copy">
      <pre ref={preRef} className={className}>
        {children}
      </pre>
      <button
        onClick={handleCopy}
        className="absolute bottom-2 right-2 p-1.5 rounded-md bg-[var(--bg-tertiary)] border border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] opacity-0 group-hover/copy:opacity-100 transition-opacity"
        title="复制到剪贴板"
      >
        {copied ? <Check className="w-3.5 h-3.5 text-[var(--success)]" /> : <Copy className="w-3.5 h-3.5" />}
      </button>
    </div>
  );
}

function ClaudeCodeMeta({ record }: { record: TokenRecord }) {
  const { user_message, cost_usd, prompt_tokens, completion_tokens, cached_tokens, cache_creation_tokens } = record;
  const parsed: Record<string, string> = {};
  const firstLine = user_message.split('\n')[0];
  const match = firstLine.match(/\[claude_code\]\s*(.*)/);
  if (match) {
    for (const part of match[1].split(/\s+/)) {
      const [k, v] = part.split('=');
      if (k && v) parsed[k] = v;
    }
  }

  const promptSection = user_message.match(/--- Prompt ---\n([\s\S]*)/);
  const promptText = promptSection ? promptSection[1].trim() : '';

  const nonCachedInput = prompt_tokens - (cached_tokens || 0) - (cache_creation_tokens || 0);

  return (
    <div className="space-y-2">
      {/* Meta bar */}
      <div className="flex flex-wrap gap-3 py-1.5 px-3 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)]">
        <div className="flex items-center gap-1.5">
          <span className="text-base">💻</span>
          <span className="font-medium text-[var(--accent)]">Claude Code</span>
        </div>
        {parsed.session && (
          <div>
            <span className="text-[var(--text-secondary)]">Session: </span>
            <span className="font-mono text-[10px]">{parsed.session}</span>
          </div>
        )}
        {parsed.turns && (
          <div>
            <span className="text-[var(--text-secondary)]">Turns: </span>
            <span className="font-medium">{parsed.turns}</span>
          </div>
        )}
        {parsed.duration && (
          <div>
            <span className="text-[var(--text-secondary)]">Duration: </span>
            <span className="font-medium">{parsed.duration}</span>
          </div>
        )}
        {cost_usd > 0 && (
          <div>
            <span className="text-[var(--text-secondary)]">Cost: </span>
            <span className="font-medium text-amber-400">${cost_usd.toFixed(4)}</span>
          </div>
        )}
      </div>

      {/* Token breakdown */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <div className="px-2.5 py-1.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)]">
          <div className="text-[10px] text-[var(--text-secondary)]">Input (non-cached)</div>
          <div className="text-sm font-medium text-cyan-400">{formatTokens(Math.max(0, nonCachedInput))}</div>
        </div>
        <div className="px-2.5 py-1.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)]">
          <div className="text-[10px] text-[var(--text-secondary)]">Cache Read 🎯</div>
          <div className="text-sm font-medium text-emerald-400">{formatTokens(cached_tokens || 0)}</div>
        </div>
        <div className="px-2.5 py-1.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)]">
          <div className="text-[10px] text-[var(--text-secondary)]">Cache Write ✍️</div>
          <div className="text-sm font-medium text-amber-400">{formatTokens(cache_creation_tokens || 0)}</div>
        </div>
        <div className="px-2.5 py-1.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)]">
          <div className="text-[10px] text-[var(--text-secondary)]">Output</div>
          <div className="text-sm font-medium text-purple-400">{formatTokens(completion_tokens)}</div>
        </div>
      </div>

      {/* Prompt */}
      {promptText && (
        <div>
          <p className="text-[var(--text-secondary)] mb-1">Prompt:</p>
          <CopyablePre className="bg-[var(--bg-primary)] rounded-lg p-3 text-xs whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
            {promptText}
          </CopyablePre>
        </div>
      )}
    </div>
  );
}

function RecordRow({
  record: r,
  expanded,
  onToggle,
}: {
  record: TokenRecord;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className="border-b border-[var(--border)]/50 hover:bg-[var(--bg-tertiary)]/30 cursor-pointer"
        onClick={onToggle}
      >
        <td className="px-4 py-2.5 text-xs text-[var(--text-secondary)] whitespace-nowrap">
          {formatTime(r.timestamp)}
        </td>
        <td className="px-4 py-2.5 font-mono text-xs truncate" title={r.model}>
          {shortModel(r.model)}
        </td>
        <td className="px-4 py-2.5 text-center">
          <ModelRoleIcon role={r.model_role || 'default'} />
        </td>
        <td className="px-4 py-2.5 text-xs">{r.provider}</td>
        <td className="px-4 py-2.5 text-right text-cyan-400 text-xs">{formatTokens(r.prompt_tokens)}</td>
        <td className="px-4 py-2.5 text-right text-emerald-400 text-xs">{formatTokens(r.completion_tokens)}</td>
        <td className="px-4 py-2.5 text-center">
          {formatCacheStatus(r.cached_tokens || 0, r.cache_creation_tokens || 0)}
        </td>
        <td className="px-4 py-2.5 text-center">
          <span
            className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${
              r.finish_reason === 'tool_use' || r.finish_reason === 'tool_calls'
                ? 'bg-amber-500/15 text-amber-400'
                : r.finish_reason === 'end_turn' || r.finish_reason === 'stop'
                  ? 'bg-emerald-500/15 text-emerald-400'
                  : 'bg-gray-500/15 text-gray-400'
            }`}
          >
            {r.finish_reason || '—'}
          </span>
        </td>
        <td className="px-4 py-2.5 text-right font-medium text-xs">{formatTokens(r.total_tokens)}</td>
        <td className="px-4 py-2.5 text-right text-xs">
          {r.cost_usd > 0 ? (
            <span className="text-amber-400 font-medium">${r.cost_usd.toFixed(4)}</span>
          ) : (
            <span className="text-[var(--text-secondary)]">—</span>
          )}
        </td>
        <td className="px-4 py-2.5 text-center">
          {expanded ? (
            <ChevronUp className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="bg-[var(--bg-tertiary)]/20 border-b border-[var(--border)]/50">
          <td colSpan={11} className="px-4 py-3 overflow-hidden">
            <div className="space-y-2 text-xs min-w-0">
              <div>
                <span className="text-[var(--text-secondary)]">Session:</span>{' '}
                <span className="font-mono">{r.session_key || '—'}</span>
              </div>
              {r.model_role === 'claude_code' && <ClaudeCodeMeta record={r} />}
              {r.user_message && r.model_role !== 'claude_code' && (
                <div>
                  <p className="text-[var(--text-secondary)] mb-1">用户输入:</p>
                  <CopyablePre className="bg-[var(--bg-primary)] rounded-lg p-3 text-xs whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
                    {r.user_message}
                  </CopyablePre>
                </div>
              )}
              {r.output_content && (
                <div>
                  <p className="text-[var(--text-secondary)] mb-1">模型输出:</p>
                  <CopyablePre className="bg-[var(--bg-primary)] rounded-lg p-3 text-xs whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
                    {r.output_content}
                  </CopyablePre>
                </div>
              )}
              {r.system_prompt_preview && (
                <div>
                  <p className="text-[var(--text-secondary)] mb-1">系统提示词:</p>
                  <CopyablePre className="bg-[var(--bg-primary)] rounded-lg p-3 text-xs whitespace-pre-wrap break-all max-h-32 overflow-y-auto text-[var(--text-secondary)]">
                    {r.system_prompt_preview}
                  </CopyablePre>
                </div>
              )}
              {r.conversation_history && (
                <div>
                  <p className="text-[var(--text-secondary)] mb-1">对话历史:</p>
                  <CopyablePre className="bg-[var(--bg-primary)] rounded-lg p-3 text-xs whitespace-pre-wrap break-all max-h-64 overflow-y-auto text-[var(--text-secondary)]">
                    {(() => {
                      try {
                        return JSON.stringify(JSON.parse(r.conversation_history), null, 2);
                      } catch {
                        return r.conversation_history;
                      }
                    })()}
                  </CopyablePre>
                </div>
              )}
              {r.full_request_payload && r.full_request_payload.length > 0 && (
                <div>
                  <p className="text-[var(--text-secondary)] mb-1">完整 API 请求:</p>
                  <CopyablePre className="bg-[var(--bg-primary)] rounded-lg p-3 text-xs whitespace-pre-wrap break-all max-h-64 overflow-y-auto text-[var(--text-secondary)]">
                    {(() => {
                      try {
                        return JSON.stringify(JSON.parse(r.full_request_payload), null, 2);
                      } catch {
                        return r.full_request_payload;
                      }
                    })()}
                  </CopyablePre>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function PageNumbers({ current, total, onPage }: { current: number; total: number; onPage: (p: number) => void }) {
  const pages: (number | '...')[] = [];
  const maxVisible = 7;

  if (total <= maxVisible) {
    for (let i = 0; i < total; i++) pages.push(i);
  } else {
    pages.push(0);
    if (current > 3) pages.push('...');
    const lo = Math.max(1, current - 1);
    const hi = Math.min(total - 2, current + 1);
    for (let i = lo; i <= hi; i++) pages.push(i);
    if (current < total - 4) pages.push('...');
    pages.push(total - 1);
  }

  return (
    <>
      {pages.map((p, i) =>
        p === '...' ? (
          <span key={`e${i}`} className="px-1 text-xs text-[var(--text-secondary)]">…</span>
        ) : (
          <button
            key={p}
            onClick={() => onPage(p)}
            className={cn(
              'min-w-[28px] px-1.5 py-1 rounded text-xs font-medium transition-colors',
              p === current
                ? 'bg-[var(--accent)] text-white'
                : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
            )}
          >
            {p + 1}
          </button>
        ),
      )}
    </>
  );
}
