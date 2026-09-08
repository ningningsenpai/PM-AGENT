import { request } from '@/api/http'
import { useMock } from '@/mock'
import type {
  Conversation,
  ChatMessage,
  ContextEntry,
  UpdateEntry,
  Snapshot,
  Run,
  OperationKind,
  LearningDraft,
  DraftCandidate,
  ContextChange,
} from './types'
function realMode() {
  if (useMock) throw new Error('此功能需要连接真实服务，请关闭演示模式')
}
export function listConversations(projectId: string) {
  realMode()
  return request<Conversation[]>({
    url: '/api/v1/agent/conversations',
    params: { projectId },
  })
}
export function createConversation(projectId: string, title?: string) {
  realMode()
  return request<Conversation>({
    url: '/api/v1/agent/conversations',
    method: 'post',
    data: { projectId, title },
  })
}
export function renameConversation(id: string, title: string) {
  realMode()
  return request<Conversation>({
    url: `/api/v1/agent/conversations/${id}`, method: 'patch', data: { title },
  })
}
export function listMessages(id: string) {
  realMode()
  return request<ChatMessage[]>({
    url: `/api/v1/agent/conversations/${id}/messages`,
  })
}
export function getRun(id: string) {
  realMode()
  return request<Run>({ url: `/api/v1/agent/runs/${id}` })
}
export function executeOperation(
  projectId: string,
  conversationId: string | undefined,
  kind: OperationKind,
  payload: Record<string, unknown>,
  key: string,
) {
  realMode()
  if (kind === 'learn_refine') {
    const { draftId, ...data } = payload
    if (typeof draftId !== 'string') throw new Error('请先选择学习草稿')
    return request<Run>({ url: `/api/v1/agent/learning-drafts/${draftId}/refine`,
      method: 'post', params: { projectId }, data,
      headers: { 'X-Idempotency-Key': key }, timeout: 20 * 60 * 1000 })
  }
  const conversationOperation = kind === 'chat' || kind === 'learn'
  if (conversationOperation && !conversationId) throw new Error('请先选择会话')
  return request<Run>({
    url: conversationOperation
      ? `/api/v1/agent/conversations/${conversationId}/${kind === 'chat' ? 'messages' : 'learn'}`
      : `/api/v1/projects/${projectId}/reports`,
    method: 'post',
    data:
      kind === 'learn' ? undefined : conversationOperation ? payload : { kind },
    headers: { 'X-Idempotency-Key': key },
    timeout: 20 * 60 * 1000,
  })
}
export function listEntries(projectId: string) {
  realMode()
  return request<ContextEntry[]>({
    url: '/api/v1/agent/context-entries',
    params: { projectId, effective: false },
  })
}
export function updateEntry(id: string, data: UpdateEntry, key: string) {
  realMode()
  return request<ContextEntry & { publication: Snapshot }>({
    url: `/api/v1/agent/context-entries/${id}`,
    method: 'patch',
    data,
    headers: { 'X-Idempotency-Key': key },
    timeout: 120000,
  })
}

export function listDrafts(projectId: string, conversationId?: string) {
  realMode()
  return request<LearningDraft[]>({ url: '/api/v1/agent/learning-drafts', params: { projectId, conversationId }, timeout: 120000 })
}
export function getDraft(projectId: string, id: string) {
  realMode()
  return request<LearningDraft>({ url: `/api/v1/agent/learning-drafts/${id}`, params: { projectId }, timeout: 120000 })
}
export function editDraft(projectId: string, id: string, version: number, candidates: DraftCandidate[], reason: string) {
  realMode()
  return request<LearningDraft>({ url: `/api/v1/agent/learning-drafts/${id}`, method: 'patch', params: { projectId }, data: { version, candidates, reason }, timeout: 120000 })
}
export function confirmDraft(projectId: string, id: string, version: number, candidateIds: string[]) {
  realMode()
  return request<LearningDraft>({ url: `/api/v1/agent/learning-drafts/${id}/confirm`, method: 'post', params: { projectId }, data: { version, candidateIds }, timeout: 120000 })
}
export function rebaseDraft(projectId: string, id: string, version: number) {
  realMode()
  return request<LearningDraft>({ url: `/api/v1/agent/learning-drafts/${id}/rebase`, method: 'post', params: { projectId }, data: { version }, timeout: 120000 })
}
export function listChanges(projectId: string, entryId: string) {
  realMode()
  return request<ContextChange[]>({ url: '/api/v1/agent/context-entries/changes', params: { projectId, entryId }, timeout: 120000 })
}
export function publishEntries(projectId: string) {
  realMode()
  return request<Record<string, Snapshot>>({
    url: '/api/v1/agent/context-entries/publish',
    method: 'post',
    params: { projectId },
    timeout: 120000,
  })
}
