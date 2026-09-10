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
export type EntryKind = 'term' | 'habit' | 'short_memory' | 'long_memory' | 'project_rule'
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
  conditions: string[]
  relatedEntryIds: string[]
}
export interface UpdateEntry {
  projectId: string
  version: number
  reason: string
  content?: string
  status?: EntryStatus
  expiresAt?: string | null
  kind?: EntryKind
  conditions?: string[]
  aliases?: string[]
  canonical?: string
}
export type OperationKind = 'chat' | 'learn' | 'learn_refine' | 'development' | 'risk'
export interface PendingOperation {
  key: string
  kind: OperationKind
  payload: Record<string, unknown>
  runId?: string
  terminal: boolean
  startedAt?: string
}

export interface LearningProposal {
  kind: EntryKind
  scope: 'user' | 'project'
  key: string
  content: string
  sourceMessageId: string
  sourceQuote: string
  confirmed: boolean
  replacesEntryId: string | null
  invalidate: boolean
  aliases: string[]
  canonical: string | null
  expiresAt: string | null
  conditions: string[]
  relatedEntryIds: string[]
  coexistReason: string | null
  targetFile: 'project_specification.json' | 'short_term_memory.json' | 'long_term_memory.json'
    | 'user_habits/work.json' | 'user_habits/thinking.json'
    | 'user_habits/specification.json' | 'user_habits/tooling.json' | 'user_habits/life.json'
  targetSection: 'development_approach' | 'technical_constraints' | 'coding_rules'
    | 'document_rules' | 'risk_rules' | null
}
export interface DraftCandidate { id: string; proposal: LearningProposal }
export interface LearningDraft {
  id: string
  projectId: string
  conversationId: string
  version: number
  state: 'pending' | 'updating' | 'partial' | 'applied' | 'discarded'
  createdAt: string
  candidates: DraftCandidate[]
  existing: ContextEntry[]
  messages: { id: string; content: string }[]
  feedback: { id: string; text: string; candidateIds: string[] }[]
  history: { version: number; candidates: DraftCandidate[]; reason: string }[]
  conflicts: { leftId: string; rightId: string; left: string; right: string }[]
  plan: { version: number; candidateIds: string[] } | null
  publications: Record<string, { published: boolean; version?: number; error?: string | null }>
  replacementDraftId?: string
}
export interface ContextChange {
  entryId?: string
  version?: number
  reason: string
  before?: Partial<ContextEntry>
  after?: Partial<ContextEntry>
  proposal?: Partial<ContextEntry>
  sourceMessageId?: string | null
}
