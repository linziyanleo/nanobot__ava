export interface ConfigItem {
  name: string
  path: string
  exists: boolean
}

export interface ConfigData {
  content: string
  mtime: number
  format: string
}

export interface ContextCompressionConfig {
  enabled: boolean
  maxChars: number
  recentTurns: number
  minRecentTurns: number
  maxOldTurns: number
  enableHistoryLookupHint: boolean
  protectedRecentMessages: number
  bootstrapMaxChars: number
}

export interface InLoopTruncationConfig {
  enabled: boolean
  readFile: number
  exec: number
  webFetch: number
  default: number
}

export interface AgentDefaults {
  workspace: string
  model: string
  visionModel: string | null
  miniModel: string | null
  memoryTier?: string | null
  provider?: string
  maxTokens: number
  temperature: number
  maxToolIterations: number
  memoryWindow?: number
  reasoningEffort?: string | null
  contextCompression?: ContextCompressionConfig
  inLoopTruncation?: InLoopTruncationConfig
}

export interface ChannelBase {
  enabled: boolean
  [key: string]: unknown
}

export interface ProviderConfig {
  apiKey: string
  apiBase: string | null
  extraHeaders: Record<string, string> | null
}

export interface MCPServerConfig {
  command: string
  args: string[]
  env: Record<string, string>
  url: string
  headers: Record<string, string>
  toolTimeout: number
}

export interface WebSearchConfig {
  apiKey: string
  maxResults: number
}

export interface WebToolsConfig {
  proxy: string | null
  search: WebSearchConfig
}

export interface ExecToolConfig {
  timeout: number
  pathAppend?: string
}

export interface ToolsConfig {
  web?: WebToolsConfig
  exec?: ExecToolConfig
  restrictToWorkspace: boolean
  mcpServers?: Record<string, MCPServerConfig>
}

export interface HeartbeatConfig {
  enabled: boolean
  intervalS: number
}

export interface ConsoleConfigType {
  enabled: boolean
  port: number
  secretKey: string
  tokenExpireMinutes: number
}

export interface GatewayConfig {
  host: string
  port: number
  heartbeat?: HeartbeatConfig
  console?: ConsoleConfigType
}

export interface NanobotConfig {
  agents: {
    defaults: AgentDefaults
  }
  channels: Record<string, ChannelBase>
  providers: Record<string, ProviderConfig>
  gateway: GatewayConfig
  tools: ToolsConfig
}
