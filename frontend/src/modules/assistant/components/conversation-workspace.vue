<template>
  <div class="conversation-workspace">
    <div class="conversation-body surface">
      <header class="conversation-head">
        <div class="conversation-heading">
          <div class="conversation-title">
            <h2 :title="conversation.title">{{ conversation.title }}</h2>
            <n-button quaternary circle size="small" aria-label="修改会话名称" title="修改会话名称" :disabled="locked || renaming" @click="openRename">
              <template #icon><CreateOutline /></template>
            </n-button>
          </div>
          <small class="muted">会话记录自动保存 · 普通问答</small>
        </div>
      </header>
      <div ref="messageViewport" class="messages" @scroll="onMessageScroll">
        <RequestError :message="error" retry @retry="load" />
        <div v-if="loading" class="muted">正在读取历史消息…</div>
        <div v-else-if="!visibleMessages.length" class="chat-welcome">
          <img :src="assistantImage" alt="PM 助手" />
          <h2>从项目里的一个问题开始</h2>
          <p>我会根据已解析的资料回答，并保留工具调用记录。</p>
          <n-space justify="center"
            ><n-button
              v-for="prompt in prompts"
              :key="prompt"
              @click="draft = prompt"
              >{{ prompt }}</n-button
            ></n-space
          >
        </div>
        <article
          v-for="item in visibleMessages"
          :key="item.id"
          :class="['message', item.role === 'user' ? 'user' : 'assistant']"
        >
          <div class="message-meta">
            {{ item.role === 'user' ? '你' : 'PM 助手' }} ·
            {{ formatDate(item.createdAt)
            }}<span v-if="item.id.startsWith('pending:')">{{ pendingStatus }}</span><n-button
              v-if="item.runId"
              text
              size="tiny"
              :disabled="operation.unresolved.value || operation.busy.value"
              @click="operation.track(item.runId)"
              >查看运行</n-button
            >
          </div>
          <SafeMarkdown :content="item.content" />
        </article>
        <div v-if="operation.pending.value?.kind === 'chat' && operation.unresolved.value" class="reply-status" role="status">
          {{ operation.busy.value || operation.run.value?.status === 'running' ? 'PM 助手正在处理你的问题…' : '请求结果尚未确认，请使用下方“查询 / 恢复”。' }}
        </div>
        <n-alert v-if="operation.run.value?.operation === 'chat' && operation.run.value.status === 'failed'" type="warning">
          本轮回答生成失败：{{ operation.run.value.error || '请查看运行记录' }}
        </n-alert>
        <LearningResults :project-id="projectId" :conversation-id="conversation.id" :operation="operation" :disabled="disabled" @busy="reviewBusy = $event" @changed="emit('changed')" />
      </div>
      <div class="composer">
        <RequestError :message="operation.error.value" />
        <n-alert v-if="operation.unresolved.value" type="info"
          ><span>{{
            operation.busy.value || operation.run.value?.status === 'running'
              ? '正在处理，完成后自动更新。'
              : '有一项操作尚未确认结果。请先恢复，避免重复执行。'
          }}</span
          ><n-button
            size="small"
            :loading="operation.busy.value"
            @click="operation.recover"
            >查询 / 恢复</n-button
          ></n-alert
        >
        <n-input
          v-model:value="draft"
          type="textarea"
          placeholder="输入项目问题，Enter 发送，Shift + Enter 换行"
          :maxlength="16000"
          show-count
          :autosize="{ minRows: 2, maxRows: 4 }"
          :disabled="locked"
          @keydown="onComposerKeydown"
        />
        <div class="composer-foot">
          <small>Enter 发送 · Shift + Enter 换行<br />回答请核对来源；明确规则会自动记录，模糊内容会请求确认。</small
          ><n-button
            type="primary"
            :loading="operation.busy.value"
            :disabled="locked || !draft.trim()"
            @click="send"
            >发送消息</n-button
          >
        </div>
      </div>
    </div>
    <aside class="surface padded run-panel">
      <RunDetail :run="operation.run.value" />
      <div class="assistant-note">
        <h4>本轮能力</h4>
        <p>读取项目资料、查询上下文、生成建议。任务变更和审批执行暂未开放。</p>
        <p>规则、记忆与项目偏好由对话多维分析自动识别。</p>
      </div>
    </aside>
    <n-modal v-model:show="showRename" preset="card" title="修改会话名称" style="width: 460px" :closable="!renaming" :mask-closable="!renaming" :close-on-esc="!renaming">
      <n-input v-model:value="renameTitle" placeholder="输入会话名称" :maxlength="128" show-count autofocus :disabled="renaming" @keydown="onRenameKeydown" />
      <RequestError :message="renameError" />
      <template #footer><n-space justify="end">
        <n-button :disabled="renaming" @click="showRename = false">取消</n-button>
        <n-button type="primary" :loading="renaming" :disabled="renaming || !renameTitle.trim()" @click="rename">保存名称</n-button>
      </n-space></template>
    </n-modal>
  </div>
</template>
<script setup lang="ts">
import { computed, nextTick, onMounted, onScopeDispose, ref, watch } from 'vue'
import { CreateOutline } from '@vicons/ionicons5'
import { renameConversation } from '../api'
import { shouldSendOnEnter, useConversationMessages } from '../conversation-messages'
import type { Conversation } from '../types'
import SafeMarkdown from '@/shared/components/safe-markdown.vue'
import RequestError from '@/shared/components/request-error.vue'
import RunDetail from './run-detail.vue'
import LearningResults from './learning-results.vue'
import assistantImage from '@/assets/figma/assistant.png'
import { errorMessage, formatDate } from '@/shared/utils/format'
const props = defineProps<{
  projectId: string
  conversation: Conversation
  disabled?: boolean
}>()
const emit = defineEmits<{ changed: []; busy: [value: boolean]; renamed: [conversation: Conversation] }>()
const chat = useConversationMessages(props.projectId, props.conversation.id, () => emit('changed'))
const { operation, messages, visibleMessages, loading, error, load } = chat
const draft = ref('')
const messageViewport = ref<HTMLElement | null>(null)
const stickToBottom = ref(true)
const showRename = ref(false)
const renameTitle = ref('')
const renameError = ref('')
const renaming = ref(false)
const reviewBusy = ref(false)
const prompts = ['概括当前项目的主要模块', '项目目前有哪些值得关注的风险？']
const locked = computed(
  () =>
    operation.busy.value ||
    operation.unresolved.value ||
    loading.value ||
    reviewBusy.value ||
    Boolean(props.disabled),
)
const pendingStatus = computed(() => {
  if (operation.error.value)
    return operation.unresolved.value ? '发送结果待核对' : '发送失败'
  if (operation.run.value && operation.run.value.status !== 'running')
    return '正在同步消息记录'
  return '正在发送，等待回复'
})
let active = true
onScopeDispose(() => {
  active = false
})
watch(
  () => operation.busy.value || reviewBusy.value,
  (value) => emit('busy', value),
  { flush: 'sync' },
)
onMounted(async () => {
  await load()
  if (!active) return
  if (operation.pending.value?.runId) void operation.recover()
  else if (!operation.pending.value && props.conversation.activeRunId)
    void operation.track(props.conversation.activeRunId)
})
function onMessageScroll() {
  const viewport = messageViewport.value
  if (viewport) stickToBottom.value = viewport.scrollHeight - viewport.clientHeight - viewport.scrollTop < 64
}
async function scrollToLatest() {
  await nextTick()
  const viewport = messageViewport.value
  if (active && viewport && stickToBottom.value) viewport.scrollTop = viewport.scrollHeight
}
watch(() => visibleMessages.value.map(item => item.id).join(','), scrollToLatest, { flush: 'post' })
function onComposerKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) event.preventDefault()
  if (shouldSendOnEnter(event)) void send()
}
async function send() {
  if (locked.value || !draft.value.trim()) return
  const content = draft.value.trim()
  draft.value = ''
  stickToBottom.value = true
  const sending = chat.send(content)
  void scrollToLatest()
  await sending
  if (active && operation.error.value && !operation.unresolved.value)
    draft.value = content
}
function openRename() {
  renameTitle.value = props.conversation.title
  renameError.value = ''
  showRename.value = true
}
function onRenameKeydown(event: KeyboardEvent) {
  if (shouldSendOnEnter(event)) { event.preventDefault(); void rename() }
}
async function rename() {
  if (renaming.value || !renameTitle.value.trim()) return
  renaming.value = true
  renameError.value = ''
  try {
    const item = await renameConversation(props.conversation.id, renameTitle.value.trim())
    if (active) { emit('renamed', item); showRename.value = false }
  } catch (e) {
    if (active) renameError.value = errorMessage(e)
  } finally {
    if (active) renaming.value = false
  }
}
</script>
<style scoped>
.conversation-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px;
  gap: 14px;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}
.conversation-body {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}
.conversation-head {
  padding: 14px 18px;
  flex: none;
  border-bottom: 1px solid var(--pm-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.conversation-heading { min-width: 0; }
.conversation-title { display: flex; align-items: center; gap: 8px; }
.conversation-title h2 { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin: 0; }
.conversation-title .n-button { flex: none; }
h2 {
  font-size: 17px;
  margin: 0 0 6px;
}
.messages {
  flex: 1;
  min-height: 0;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  overflow: auto;
  overscroll-behavior: contain;
}
.messages > * { flex-shrink: 0; }
.reply-status { color: var(--pm-text-secondary); font-size: 13px; padding: 0 8px; }
.message {
  padding: 18px;
  border: 1px solid var(--pm-border);
  border-radius: 14px;
}
.message.user {
  background: var(--pm-blue-soft);
  border-color: #dde9fb;
  margin-left: 30px;
}
.message.assistant {
  margin-right: 16px;
}
.message-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  color: var(--pm-text-secondary);
  font-size: 11px;
  margin-bottom: 12px;
}
.message-meta .n-button {
  margin-left: auto;
}
.chat-welcome {
  text-align: center;
  margin: auto;
  padding: 32px 0;
}
.chat-welcome img {
  width: 110px;
  height: 110px;
  object-fit: contain;
}
.chat-welcome p {
  color: var(--pm-text-secondary);
  font-size: 13px;
  margin-bottom: 24px;
}
.composer {
  padding: 12px 16px;
  flex: none;
  max-height: 55%;
  overflow-y: auto;
  border-top: 1px solid var(--pm-border);
  display: grid;
  gap: 12px;
}
.run-panel { min-height: 0; height: 100%; overflow-y: auto; padding: 18px; overscroll-behavior: contain; }
.composer-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.composer-foot small {
  color: var(--pm-text-muted);
  font-size: 11px;
}
.assistant-note {
  margin-top: 28px;
  padding: 16px;
  background: var(--pm-green-soft);
  border-radius: 12px;
  color: var(--pm-text-secondary);
  font-size: 12px;
  line-height: 1.8;
  overflow-wrap: anywhere;
}
.assistant-note h4 {
  margin: 0;
  color: var(--pm-green-dark);
}
@media (max-width: 1280px) {
  .conversation-workspace {
    grid-template-columns: minmax(0, 1fr) 210px;
  }
}
</style>
