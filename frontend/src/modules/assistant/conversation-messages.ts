import { computed, onScopeDispose, ref, watch } from 'vue'
import { listMessages } from './api'
import { useOperation } from './operation'
import type { ChatMessage, Run } from './types'
import { errorMessage } from '@/shared/utils/format'

export function shouldSendOnEnter(event: Pick<KeyboardEvent, 'key' | 'shiftKey' | 'isComposing' | 'keyCode' | 'repeat'>) {
  return event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229 && !event.repeat
}

export function mergePendingMessage(messages: ChatMessage[], pending: ChatMessage | null, run: Run | null) {
  if (!pending) return messages
  // 使用请求标识或运行消息 ID 对齐，不按正文去重，以保留重复提问。
  const persisted = messages.some(message => message.role === 'user' && (
    (message.requestKey && message.requestKey === pending.requestKey)
    || (run && (message.id === run.result.userMessageId || message.runId === run.runId))
  ))
  return persisted ? messages : [...messages, pending]
}

export function useConversationMessages(projectId: string, conversationId: string, onFinished: () => void) {
  const operation = useOperation(projectId, conversationId)
  const messages = ref<ChatMessage[]>([])
  const pendingMessage = ref<ChatMessage | null>(null)
  const loading = ref(false)
  const error = ref('')
  let active = true
  let generation = 0
  onScopeDispose(() => { active = false; generation++ })
  watch(() => operation.pending.value?.key, () => {
    const pending = operation.pending.value
    pendingMessage.value = pending?.kind === 'chat' && typeof pending.payload.content === 'string'
      ? { id: `pending:${pending.key}`, role: 'user', content: pending.payload.content,
        runId: pending.runId || '', requestKey: pending.key, createdAt: pending.startedAt || new Date().toISOString() }
      : null
  }, { immediate: true, flush: 'sync' })
  const visibleMessages = computed(() => mergePendingMessage(messages.value, pendingMessage.value, operation.run.value))

  async function load() {
    const current = ++generation
    loading.value = true
    error.value = ''
    try {
      const data = await listMessages(conversationId)
      if (active && current === generation) messages.value = data
    } catch (e) {
      if (active && current === generation) error.value = errorMessage(e)
    } finally {
      if (active && current === generation) loading.value = false
    }
  }
  watch(() => operation.run.value, (run) => {
    if (run && run.status !== 'running') { void load(); onFinished() }
  })
  async function send(content: string) {
    if (loading.value || operation.busy.value || operation.unresolved.value || !content.trim()) return
    await operation.start('chat', { content: content.trim() })
  }
  return { operation, messages, visibleMessages, loading, error, load, send }
}
