import type { AgentDefaults } from './types'
import { Section, renderField } from './FormWidgets'

export function AgentDefaultsSection({
  config,
  readOnly,
  onChange,
}: {
  config: AgentDefaults
  readOnly: boolean
  onChange: (c: AgentDefaults) => void
}) {
  const simpleFields: Array<{ key: keyof AgentDefaults; label: string }> = [
    { key: 'workspace', label: 'workspace' },
    { key: 'model', label: 'model' },
    { key: 'visionModel', label: 'visionModel' },
    { key: 'miniModel', label: 'miniModel' },
    { key: 'memoryTier', label: 'memoryTier' },
    { key: 'provider', label: 'provider' },
    { key: 'maxTokens', label: 'maxTokens' },
    { key: 'temperature', label: 'temperature' },
    { key: 'maxToolIterations', label: 'maxToolIterations' },
    { key: 'memoryWindow', label: 'memoryWindow' },
    { key: 'reasoningEffort', label: 'reasoningEffort' },
  ]

  return (
    <Section title="通用配置" infoKey="agents.defaults.model">
      <div className="space-y-3">
        {simpleFields.map(({ key, label }) => {
          const val = config[key];
          if (val !== undefined && typeof val === 'object' && val !== null) return null;
          return renderField(label, val, `agents.defaults.${key}`, readOnly, v => onChange({ ...config, [key]: v }));
        })}
      </div>

      {config.contextCompression && (
        <div className="mt-4">
          <Section title="上下文压缩" infoKey="agents.defaults.contextCompression.enabled" defaultOpen={false}>
            <div className="space-y-3">
              {Object.entries(config.contextCompression).map(([key, val]) =>
                renderField(key, val, `agents.defaults.contextCompression.${key}`, readOnly, v =>
                  onChange({ ...config, contextCompression: { ...config.contextCompression!, [key]: v } }),
                ),
              )}
            </div>
          </Section>
        </div>
      )}

      {config.inLoopTruncation && (
        <div className="mt-3">
          <Section title="循环内截断" infoKey="agents.defaults.inLoopTruncation.enabled" defaultOpen={false}>
            <div className="space-y-3">
              {Object.entries(config.inLoopTruncation).map(([key, val]) => {
                if (typeof val === 'function') return null;
                return renderField(key, val, `agents.defaults.inLoopTruncation.${key}`, readOnly, v =>
                  onChange({ ...config, inLoopTruncation: { ...config.inLoopTruncation!, [key]: v } }),
                );
              })}
            </div>
          </Section>
        </div>
      )}
    </Section>
  );
}
