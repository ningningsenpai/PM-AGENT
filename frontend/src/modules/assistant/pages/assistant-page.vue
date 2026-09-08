<template>
  <div class="page-shell assistant-page">
    <div class="page-title-row assistant-heading">
      <div class="assistant-title">
        <h1 class="page-title">PM 助手</h1>
        <span class="muted">基于项目资料问答，保留可核对的来源</span>
      </div>
      <RouterLink :to="'/projects/' + projectId">管理项目文件 →</RouterLink>
    </div>
    <RequestError :message="error" retry @retry="load" />
    <n-tabs v-model:value="tab" type="line"
      ><n-tab name="chat">项目问答</n-tab
      ><n-tab name="context">学习内容管理</n-tab></n-tabs
    >
    <div v-show="tab === 'chat'" class="assistant-grid">
      <aside class="surface conversation-list">
        <n-button
          type="primary"
          block
          :loading="creating"
          :disabled="creating || loading || operationBusy"
          @click="create"
          >新建会话</n-button
        >
        <div class="list-caption">
          <span>历史会话</span
          ><n-button text size="small" :loading="loading" :disabled="creating" @click="load"
            >刷新</n-button
          >
        </div>
        <div class="conversation-scroll">
        <n-empty
          v-if="!conversations.length && !loading"
          description="暂无会话"
        />
        <button
          v-for="item in conversations"
          :key="item.id"
          :class="[
            'conversation-item',
            { selected: item.id === conversationId },
          ]"
          :disabled="operationBusy"
          @click="select(item.id)"
        >
          <b>{{ item.title }}</b
          ><small
            >{{ formatDate(item.createdAt)
            }}{{ item.activeRunId ? ' · 运行中' : '' }}</small
          >
        </button>
        </div>
      </aside>
      <ConversationWorkspace
        v-if="selected"
        :key="selected.id"
        :project-id="projectId"
        :conversation="selected"
        :disabled="contextBusy"
        @busy="operationBusy = $event"
        @changed="changed"
        @renamed="renamed"
      />
      <section v-else class="surface padded conversation-empty">
        <n-result
          status="info"
          title="创建一个项目会话"
          description="会话按项目独立保存，刷新后可以继续。"
          ><template #footer
            ><n-button type="primary" :loading="creating" :disabled="creating || loading" @click="create"
              >开始问答</n-button
            ></template
          ></n-result
        >
      </section>
    </div>
    <section v-show="tab === 'context'" class="surface padded context-panel">
      <ContextEntries
        :project-id="projectId"
        :revision="revision"
        :disabled="operationBusy"
        @busy="contextBusy = $event"
      />
    </section>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onScopeDispose, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listConversations, createConversation } from '../api'
import type { Conversation } from '../types'
import ConversationWorkspace from '../components/conversation-workspace.vue'
import ContextEntries from '../components/context-entries.vue'
import RequestError from '@/shared/components/request-error.vue'
import { errorMessage, formatDate } from '@/shared/utils/format'
const route = useRoute()
const router = useRouter()
const projectId = String(route.params.id)
const conversations = ref<Conversation[]>([])
const loading = ref(false)
const error = ref('')
const conversationId = ref(String(route.query.conversation || ''))
const tab = ref('chat')
const revision = ref(0)
const creating = ref(false)
const operationBusy = ref(false)
const contextBusy = ref(false)
const selected = computed(() =>
  conversations.value.find((c) => c.id === conversationId.value),
)
let active = true
let generation = 0
onScopeDispose(() => {
  active = false
  generation++
})
async function load() {
  const current = ++generation
  loading.value = true
  error.value = ''
  try {
    const data = await listConversations(projectId)
    if (active && current === generation) {
      conversations.value = data
      if (!conversationId.value && data.length) await select(data[0].id)
      else if (
        conversationId.value &&
        !data.some((c) => c.id === conversationId.value)
      )
        error.value = '会话不存在或不属于当前项目，请选择其他会话'
    }
  } catch (e) {
    if (active && current === generation) error.value = errorMessage(e)
  } finally {
    if (active && current === generation) loading.value = false
  }
}
async function select(id: string) {
  conversationId.value = id
  await router.replace({ query: { ...route.query, conversation: id } })
}
async function create() {
  if (creating.value || loading.value || operationBusy.value) return
  creating.value = true
  error.value = ''
  generation++
  try {
    const item = await createConversation(projectId)
    if (active) {
      conversations.value = [item, ...conversations.value]
      await select(item.id)
    }
  } catch (e) {
    if (active)
      error.value = errorMessage(e) + '；若结果不明，请先刷新会话列表核对。'
  } finally {
    if (active) creating.value = false
  }
}
function renamed(item: Conversation) {
  conversations.value = conversations.value.map(value => value.id === item.id ? item : value)
}
function changed() {
  revision.value++
  void load()
}
watch(
  () => route.query.conversation,
  (id) => {
    if (typeof id === 'string' && id !== conversationId.value) {
      operationBusy.value = false
      conversationId.value = id
    }
  },
)
onMounted(load)
</script>
<style scoped>
.assistant-page { height: 100%; min-height: 0; gap: 12px; overflow: hidden; }
.assistant-heading { align-items: center; flex: none; }
.assistant-title { display: flex; align-items: baseline; gap: 14px; }
.assistant-title .page-title { font-size: 22px; }
.assistant-page > :deep(.n-tabs) { flex: none; }
.assistant-grid {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr);
  gap: 14px;
  flex: 1;
  min-height: 0;
  align-items: stretch;
}
.conversation-list {
  padding: 14px 10px;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.conversation-list > .n-button, .list-caption { flex: none; }
.conversation-scroll { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; }
.conversation-empty, .context-panel { min-height: 0; overflow: auto; }
.context-panel { flex: 1; }
.list-caption {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--pm-text-secondary);
  font-size: 12px;
  padding: 16px 8px 10px;
}
.conversation-item {
  display: grid;
  gap: 10px;
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  background: none;
  border-radius: 10px;
  padding: 16px 12px;
  color: var(--pm-text);
  cursor: pointer;
}
.conversation-item:hover {
  background: var(--pm-bg);
}
.conversation-item.selected {
  background: var(--pm-blue-soft);
  border-color: #d5e5fc;
}
.conversation-item small {
  font-size: 11px;
  color: var(--pm-text-secondary);
}
.conversation-item b {
  overflow-wrap: anywhere;
  font-weight: 600;
}
</style>
