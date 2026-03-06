export type SceneType = 'telegram' | 'cron' | 'heartbeat' | 'console' | 'cli' | 'feishu' | 'QQ' | 'wx' | 'discord' | 'other'

export interface SessionMeta {
  filename: string
  filepath: string
  scene: SceneType
  key: string
  created_at: string
  updated_at: string
  token_stats: {
    total_prompt_tokens: number
    total_completion_tokens: number
    total_tokens: number
    llm_calls: number
  }
}

export interface ToolCall {
  id: string
  type: 'function'
  function: { name: string; arguments: string }
}

export interface RawMessage {
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string | null | Array<{ type: string; text?: string }>
  timestamp?: string
  tool_calls?: ToolCall[]
  tool_call_id?: string
  name?: string
  reasoning_content?: string
}

export interface ToolCallWithResult {
  call: ToolCall
  result?: RawMessage
}

export interface TurnGroup {
  userMessage: RawMessage
  assistantSteps: RawMessage[]
  isComplete: boolean
  startTime?: string
  endTime?: string
  toolCalls: ToolCallWithResult[]
}

export const SCENE_LABELS: Record<SceneType, string> = {
  telegram: 'Telegram',
  cron: 'Cron',
  heartbeat: 'Heartbeat',
  console: 'Console',
  cli: 'CLI',
  feishu: 'Feishu',
  QQ: 'QQ',
  wx: 'WeChat',
  discord: 'Discord',
  other: 'Other',
}

export const SCENE_ORDER: SceneType[] = ['console', 'telegram', 'cron', 'heartbeat', 'cli', 'other']
