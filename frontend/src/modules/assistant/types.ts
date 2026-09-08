export interface Conversation {
  id: string
  projectId: string
  title: string
  learnedMessageId: string
  activeRunId: string | null
  createdAt: string
}
export interface ChatMessage {
  id: string
  role: string
  content: string
  runId: string
  createdAt: string
  requestKey?: string | null
}
export interface Run {
  runId: string
  projectId: string
  conversationId: string | null
  operation: string
  status: 'running' | 'success' | 'failed'
  traceId: string
  result: Record<string, unknown>
  error: string | null
  events: Record<string, unknown>[]
}
export type EntryKind = 'term' | 'habit' | 'short_memory' | 'long_memory'
export type EntryStatus = 'active' | 'pending' | 'invalid'
export interface Snapshot {
  version: number
  published: boolean
  error: string | null
}
export interface ContextEntry {
  id: string
  projectId: string | null
  kind: EntryKind
  content: string
  attributes: Record<string, unknown>
  status: EntryStatus
  version: number
  sourceMessageId: string | null
  expiresAt: string | null
}
export interface UpdateEntry {
  version: number
  reason: string
  content?: string
  status?: EntryStatus
  expiresAt?: string | null
  kind?: EntryKind
}
export type OperationKind = 'chat' | 'learn' | 'development' | 'risk'
export interface PendingOperation {
  key: string
  kind: OperationKind
  payload: Record<string, unknown>
  runId?: string
  terminal: boolean
  startedAt?: string
}
