import type { ContextEntry, EntryKind, LearningDraft } from './types'
import { serverDate } from '@/shared/utils/format'

export const entryKinds: Record<EntryKind, string> = {
  habit: '用户习惯', project_rule: '项目规则', term: '术语词库',
  short_memory: '短期记忆', long_memory: '长期记忆',
}
export const draftStates: Record<LearningDraft['state'], string> = {
  pending: '待确认', publishing: '发布待恢复', partial: '部分发布失败',
  published: '已发布', discarded: '未采纳',
}
export function entryState(entry: ContextEntry) {
  return entry.status === 'active' && entry.expiresAt && serverDate(entry.expiresAt).getTime() <= Date.now() ? 'expired' : entry.status
}
export function draftSummary(draft: LearningDraft) {
  return Object.entries(entryKinds).map(([kind, label]) => {
    const count = draft.candidates.filter(item => item.proposal.kind === kind).length
    return count ? `${label} ${count} 条` : ''
  }).filter(Boolean).join(' · ') || '本轮没有提取到可复用内容'
}
export function splitLines(value: string) {
  return [...new Set(value.split('\n').map(line => line.trim()).filter(Boolean))]
}
export function reconcileSelection(previousIds: string[], nextIds: string[], selectedIds: string[]) {
  const previous = new Set(previousIds)
  const selected = new Set(selectedIds)
  return nextIds.filter(id => selected.has(id) || !previous.has(id))
}
