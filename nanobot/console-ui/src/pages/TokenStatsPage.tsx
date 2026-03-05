import { useEffect, useState, useCallback, useRef } from 'react';
import { RefreshCw, BarChart3, List, ChevronDown, ChevronUp, Trash2, Copy, Check } from 'lucide-react';
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
  full_request_payload: string;
  finish_reason: string;
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

function fmtTooltip(v: number | undefined): string {
  return formatTokens(v ?? 0);
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

export default function TokenStatsPage() {
  const [view, setView] = useState<'records' | 'charts'>('records');
  const [summary, setSummary] = useState<TokenSummary | null>(null);
  const [records, setRecords] = useState<TokenRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const { isAdmin } = useAuth();
  const pageSize = 50;

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
      const r = await api<RecordsResponse>(`/stats/tokens/records?limit=${pageSize}&offset=${p * pageSize}`);
      setRecords(r.records);
      setTotal(r.total);
      setPage(p);
    } catch {
      /* ignore */
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadSummary();
    loadRecords(0);
  }, [loadSummary, loadRecords]);

  const handleReset = async () => {
    if (!confirm('确认清空所有 Token 统计数据？')) return;
    try {
      await api('/stats/tokens/reset', { method: 'POST' });
      loadSummary();
      loadRecords(0);
    } catch {
      /* ignore */
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  const pieData = summary
    ? [
        { name: 'Prompt', value: summary.totals.prompt_tokens },
        { name: 'Completion', value: summary.totals.completion_tokens },
      ]
    : [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">Token Usage</h1>
          <div className="flex bg-[var(--bg-tertiary)] rounded-lg p-0.5">
            <button
              onClick={() => setView('records')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                view === 'records'
                  ? 'bg-[var(--accent)] text-white'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`}
            >
              <List className="w-3.5 h-3.5" /> 明细
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
              <BarChart3 className="w-3.5 h-3.5" /> 聚合
            </button>
          </div>
        </div>
        <div className="flex gap-2">
          {isAdmin() && (
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--danger)]/10 text-[var(--danger)] hover:bg-[var(--danger)]/20 text-sm"
            >
              <Trash2 className="w-4 h-4" /> 清空
            </button>
          )}
          <button
            onClick={() => {
              loadSummary();
              loadRecords(page);
            }}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-sm"
          >
            <RefreshCw className="w-4 h-4" /> 刷新
          </button>
        </div>
      </div>

      {/* Overview Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-4">
            <p className="text-xs text-[var(--text-secondary)] mb-1">Total Tokens</p>
            <p className="text-xl font-bold text-[var(--accent)]">{formatTokens(summary.totals.total_tokens)}</p>
          </div>
          <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-4">
            <p className="text-xs text-[var(--text-secondary)] mb-1">LLM Calls</p>
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
      )}

      {view === 'records' ? (
        /* ============ Records View ============ */
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-[var(--text-secondary)] text-xs">
                  <th className="text-left px-4 py-3 font-medium">时间</th>
                  <th className="text-left px-4 py-3 font-medium">模型</th>
                  <th className="text-left px-4 py-3 font-medium">Provider</th>
                  <th className="text-right px-4 py-3 font-medium">Prompt</th>
                  <th className="text-right px-4 py-3 font-medium">Completion</th>
                  <th className="text-center px-4 py-3 font-medium">Type</th>
                  <th className="text-right px-4 py-3 font-medium">Total</th>
                  <th className="text-center px-4 py-3 font-medium w-10"></th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={8} className="text-center py-8 text-[var(--text-secondary)]">
                      加载中...
                    </td>
                  </tr>
                ) : records.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="text-center py-8 text-[var(--text-secondary)]">
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
              <div className="flex gap-1">
                <button
                  disabled={page === 0}
                  onClick={() => loadRecords(page - 1)}
                  className="px-3 py-1 rounded text-xs bg-[var(--bg-tertiary)] text-[var(--text-secondary)] disabled:opacity-30 hover:text-[var(--text-primary)]"
                >
                  上一页
                </button>
                <button
                  disabled={page >= totalPages - 1}
                  onClick={() => loadRecords(page + 1)}
                  className="px-3 py-1 rounded text-xs bg-[var(--bg-tertiary)] text-[var(--text-secondary)] disabled:opacity-30 hover:text-[var(--text-primary)]"
                >
                  下一页
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
        <td className="px-4 py-2.5 font-mono text-xs">{shortModel(r.model)}</td>
        <td className="px-4 py-2.5 text-xs">{r.provider}</td>
        <td className="px-4 py-2.5 text-right text-cyan-400 text-xs">{formatTokens(r.prompt_tokens)}</td>
        <td className="px-4 py-2.5 text-right text-emerald-400 text-xs">{formatTokens(r.completion_tokens)}</td>
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
        <td className="px-4 py-2.5 text-center">
          {expanded ? (
            <ChevronUp className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="bg-[var(--bg-tertiary)]/20">
          <td colSpan={8} className="px-4 py-3">
            <div className="space-y-2 text-xs">
              <div>
                <span className="text-[var(--text-secondary)]">Session:</span>{' '}
                <span className="font-mono">{r.session_key || '—'}</span>
              </div>
              {r.user_message && (
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
              {r.full_request_payload && (
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
