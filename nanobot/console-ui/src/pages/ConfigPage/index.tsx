import { useEffect, useState, useRef, useCallback } from 'react'
import { Save, RefreshCw, Eye } from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../stores/auth'
import type { ConfigItem, ConfigData, NanobotConfig, ChannelBase, CronStore } from './types'
import { Section } from './FormWidgets'
import { AgentDefaultsSection } from './AgentDefaultsSection'
import { ChannelSection } from './ChannelSection'
import { ProviderSection } from './ProviderSection'
import { GatewaySection } from './GatewaySection'
import { ToolsSection } from './ToolsSection'
import { TokenStatsSection } from './TokenStatsSection'
import { CronJobsEditor } from './CronJobsEditor'

const TAB_LABELS: Record<string, string> = {
  'config.json': '通用配置',
  'cron/jobs.json': '定时任务',
}

function getTabLabel(name: string): string {
  return TAB_LABELS[name] ?? name
}

function isCronConfig(name: string): boolean {
  return name === 'cron/jobs.json'
}

export default function ConfigPage() {
  const [configs, setConfigs] = useState<ConfigItem[]>([])
  const [selected, setSelected] = useState<string>('')
  const [data, setData] = useState<ConfigData | null>(null)
  const [parsed, setParsed] = useState<NanobotConfig | null>(null)
  const [cronStore, setCronStore] = useState<CronStore | null>(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [dirty, setDirty] = useState(false)
  const { canEdit, isAdmin } = useAuth()

  const originalRef = useRef<string>('')

  useEffect(() => {
    api<ConfigItem[]>('/config/list').then((list) => {
      setConfigs(list)
      if (list.length > 0) setSelected(list[0].name)
    })
  }, [])

  useEffect(() => {
    if (selected) loadConfig(selected)
  }, [selected])

  const loadConfig = async (name: string) => {
    try {
      const d = await api<ConfigData>(`/config/${name}`)
      setData(d)
      originalRef.current = d.content
      try {
        const obj = JSON.parse(d.content)
        if (isCronConfig(name)) {
          setCronStore(obj)
          setParsed(null)
        } else {
          setParsed(obj)
          setCronStore(null)
        }
      } catch {
        setParsed(null)
        setCronStore(null)
      }
      setDirty(false)
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '加载失败' })
    }
  }

  const updateParsed = useCallback((updater: (prev: NanobotConfig) => NanobotConfig) => {
    setParsed((prev) => {
      if (!prev) return prev
      const next = updater(prev)
      setDirty(true)
      return next
    })
  }, [])

  const updateCronStore = useCallback((store: CronStore) => {
    setCronStore(store)
    setDirty(true)
  }, [])

  const saveConfig = async () => {
    if (!data || !selected) return
    const payload = isCronConfig(selected) ? cronStore : parsed
    if (!payload) return
    setSaving(true)
    setMessage(null)
    const content = JSON.stringify(payload, null, 2)
    try {
      const result = await api<{ mtime: number }>(`/config/${selected}`, {
        method: 'PUT',
        body: JSON.stringify({ content, mtime: data.mtime }),
      })
      setData({ ...data, content, mtime: result.mtime })
      originalRef.current = content
      setDirty(false)
      setMessage({ type: 'success', text: '保存成功' })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '保存失败' })
    } finally {
      setSaving(false)
    }
  }

  const revealSecret = async (fieldPath: string) => {
    try {
      const result = await api<{ value: string }>(`/config/${selected}/reveal`, {
        method: 'POST',
        body: JSON.stringify({ field_path: fieldPath }),
      })
      alert(`${fieldPath}: ${result.value}`)
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '解密失败' })
    }
  }

  const readOnly = !canEdit()
  const showCron = isCronConfig(selected)
  const hasContent = showCron ? !!cronStore : !!parsed

  const tabBar = (
    <div className="flex gap-1 mb-3">
      {configs.map((c) => (
        <button
          key={c.name}
          onClick={() => setSelected(c.name)}
          className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
            selected === c.name
              ? 'bg-[var(--accent)] text-white'
              : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
          }`}
        >
          {getTabLabel(c.name)}
        </button>
      ))}
    </div>
  )

  if (!hasContent) {
    return (
      <div className="h-[calc(100vh-3rem)] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold">配置管理</h1>
        </div>
        {tabBar}
        <div className="text-center py-20 text-[var(--text-secondary)]">加载中...</div>
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-3rem)] flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">配置管理</h1>
        <div className="flex items-center gap-2">
          {!showCron && isAdmin() && selected && (
            <button
              onClick={() => {
                const path = prompt('输入字段路径 (例如 providers.openai.apiKey):')
                if (path) revealSecret(path)
              }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-sm transition-colors"
            >
              <Eye className="w-4 h-4" />
              解密字段
            </button>
          )}
          <button
            onClick={() => loadConfig(selected)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-sm transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            重载
          </button>
          {canEdit() && (
            <button
              onClick={saveConfig}
              disabled={!dirty || saving}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium transition-colors disabled:opacity-40"
            >
              <Save className="w-4 h-4" />
              {saving ? '保存中...' : '保存'}
            </button>
          )}
        </div>
      </div>

      {message && (
        <div className={`mb-3 p-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-[var(--success)]/10 text-[var(--success)]' : 'bg-[var(--danger)]/10 text-[var(--danger)]'}`}>
          {message.text}
        </div>
      )}

      {tabBar}

      <div className="flex-1 overflow-y-auto space-y-4 pb-8">
        {showCron && cronStore ? (
          <CronJobsEditor store={cronStore} readOnly={readOnly} onChange={updateCronStore} />
        ) : parsed ? (
          <>
            {parsed.agents?.defaults && (
              <AgentDefaultsSection
                config={parsed.agents.defaults}
                readOnly={readOnly}
                onChange={(defaults) => updateParsed((p) => ({ ...p, agents: { ...p.agents, defaults } }))}
              />
            )}

            {parsed.token_stats && (
              <TokenStatsSection
                config={parsed.token_stats}
                readOnly={readOnly}
                onChange={(token_stats) => updateParsed((p) => ({ ...p, token_stats }))}
              />
            )}

            {parsed.channels && (
              <Section title="消息渠道" infoKey="channels" defaultOpen={true}>
                <div className="space-y-3">
                  {Object.entries(parsed.channels).map(([name, channelConfig]) => {
                    if (typeof channelConfig !== 'object' || channelConfig === null) return null
                    if (!('enabled' in channelConfig)) return null
                    return (
                      <ChannelSection
                        key={name}
                        name={name}
                        config={channelConfig as ChannelBase}
                        readOnly={readOnly}
                        onChange={(c) => updateParsed((p) => ({ ...p, channels: { ...p.channels, [name]: c } }))}
                      />
                    )
                  })}
                </div>
              </Section>
            )}

            {parsed.providers && (
              <Section title="LLM 服务商" infoKey="providers" defaultOpen={true}>
                <div className="space-y-3">
                  {Object.entries(parsed.providers).map(([name, providerConfig]) => (
                    <ProviderSection
                      key={name}
                      name={name}
                      config={providerConfig}
                      readOnly={readOnly}
                      onChange={(c) => updateParsed((p) => ({ ...p, providers: { ...p.providers, [name]: c } }))}
                    />
                  ))}
                </div>
              </Section>
            )}

            {parsed.gateway && (
              <GatewaySection
                config={parsed.gateway}
                readOnly={readOnly}
                onChange={(gateway) => updateParsed((p) => ({ ...p, gateway }))}
              />
            )}

            {parsed.tools && (
              <ToolsSection
                config={parsed.tools}
                readOnly={readOnly}
                onChange={(tools) => updateParsed((p) => ({ ...p, tools }))}
              />
            )}
          </>
        ) : null}
      </div>
    </div>
  )
}
