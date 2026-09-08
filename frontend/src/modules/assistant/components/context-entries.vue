<template>
  <section class="context-panel">
    <div class="page-title-row">
      <div>
        <h2>已学习内容</h2>
        <p class="muted">
          由你显式触发学习，生效内容会用于后续问答。通用内容在个人项目间共享。
        </p>
      </div>
      <n-space
        ><n-button :loading="loading" :disabled="saving" @click="load"
          >刷新</n-button
        ><n-button :loading="publishing" :disabled="saving" @click="publish"
          >重发快照</n-button
        ></n-space
      >
    </div>
    <RequestError :message="error" />
    <n-alert v-if="notice" :type="snapshotFailed ? 'warning' : 'success'">{{
      notice
    }}</n-alert>
    <div class="toolbar">
      <n-input
        v-model:value="query"
        placeholder="查找已学习内容"
        clearable
        style="max-width: 300px"
      /><n-select
        v-model:value="filter"
        :options="[
          { label: '全部状态', value: 'all' },
          ...statuses,
          { label: '已过期', value: 'expired' },
        ]"
        style="width: 170px"
      /><span class="muted">{{ filtered.length }} 条</span>
    </div>
    <n-spin :show="loading"
      ><n-empty
        v-if="!entries.length && !loading && !error"
        description="尚无学习内容。在会话中补充项目信息，再点击“学习本会话”。"
      />
      <article v-for="entry in filtered" :key="entry.id" class="entry-card">
        <div class="entry-meta">
          <n-tag
            size="small"
            :type="state(entry) === 'active' ? 'success' : 'default'"
            >{{ stateLabels[state(entry)] }}</n-tag
          ><span
            >{{ kinds[entry.kind] }} ·
            {{ entry.projectId ? '当前项目' : '个人通用' }} · 版本
            {{ entry.version }}</span
          ><n-button
            size="small"
            :disabled="saving || publishing || disabled"
            @click="edit(entry)"
            >查看与纠正</n-button
          >
        </div>
        <p>{{ entry.content }}</p>
        <small class="muted"
          >来源消息：{{ entry.sourceMessageId || '暂未提供'
          }}<template v-if="entry.expiresAt">
            · 到期时间 {{ formatDate(entry.expiresAt) }}</template
          ></small
        >
      </article>
    </n-spin>
    <n-modal
      v-model:show="editing"
      preset="card"
      title="纠正学习内容"
      style="width: 660px"
      :mask-closable="!saving"
      :close-on-esc="!saving"
      :closable="!saving"
    >
      <template v-if="selected"
        ><n-alert v-if="selected.kind === 'term'" type="info"
          >词条映射请在会话中说明纠正内容，再显式学习。这里可调整词条状态。</n-alert
        >
        <n-form label-placement="top"
          ><n-form-item label="内容"
            ><n-input
              v-model:value="draft.content"
              type="textarea"
              :disabled="selected.kind === 'term'"
              :maxlength="4000"
              :autosize="{ minRows: 4, maxRows: 10 }" /></n-form-item
          ><n-form-item label="状态"
            ><n-select
              v-model:value="draft.status"
              :options="statuses" /></n-form-item
          ><n-form-item label="纠正原因（必填）"
            ><n-input
              v-model:value="draft.reason"
              :maxlength="1000"
              placeholder="说明为什么需要调整这条内容" /></n-form-item
          ><n-checkbox
            v-if="selected.kind === 'short_memory'"
            v-model:checked="draft.promote"
            >确认为长期记忆</n-checkbox
          ></n-form
        >
        <details>
          <summary>来源与属性</summary>
          <pre>{{ JSON.stringify(selected.attributes, null, 2) }}</pre>
        </details>
        <RequestError :message="editError" />
        <n-space justify="end"
          ><n-button :disabled="saving" @click="editing = false">取消</n-button
          ><n-button :loading="saving" type="primary" @click="save"
            >保存纠正</n-button
          ></n-space
        >
      </template>
    </n-modal>
  </section>
</template>
<script setup lang="ts">
import { computed, onScopeDispose, reactive, ref, watch } from 'vue'
import { listEntries, updateEntry, publishEntries } from '../api'
import type { ContextEntry, EntryStatus, UpdateEntry } from '../types'
import RequestError from '@/shared/components/request-error.vue'
import { errorMessage, formatDate, serverDate } from '@/shared/utils/format'
const props = defineProps<{
  projectId: string
  revision?: number
  disabled?: boolean
}>()
const emit = defineEmits<{ busy: [value: boolean] }>()
const entries = ref<ContextEntry[]>([])
const loading = ref(false)
const saving = ref(false)
const publishing = ref(false)
const error = ref('')
const editError = ref('')
const notice = ref('')
const snapshotFailed = ref(false)
const query = ref('')
const filter = ref('all')
const editing = ref(false)
const selected = ref<ContextEntry | null>(null)
const draft = reactive({
  content: '',
  status: 'active' as EntryStatus,
  reason: '',
  promote: false,
})
let active = true
let generation = 0
onScopeDispose(() => {
  active = false
  generation++
})
watch(
  () => saving.value || publishing.value,
  (value) => emit('busy', value),
  { flush: 'sync' },
)
const kinds = {
  term: '词条',
  habit: '使用习惯',
  short_memory: '短期记忆',
  long_memory: '长期记忆',
}
const stateLabels: Record<string, string> = {
  active: '有效',
  pending: '待确认',
  invalid: '已失效',
  expired: '已过期',
}
const statuses = [
  { label: '有效', value: 'active' },
  { label: '待确认', value: 'pending' },
  { label: '已失效', value: 'invalid' },
]
function state(entry: ContextEntry) {
  return entry.expiresAt && serverDate(entry.expiresAt).getTime() <= Date.now()
    ? 'expired'
    : entry.status
}
const filtered = computed(() =>
  entries.value.filter(
    (e) =>
      e.content.includes(query.value.trim()) &&
      (filter.value === 'all' || state(e) === filter.value),
  ),
)
async function load() {
  const version = ++generation
  loading.value = true
  error.value = ''
  try {
    const data = await listEntries(props.projectId)
    if (active && version === generation) entries.value = data
  } catch (e) {
    if (active && version === generation) error.value = errorMessage(e)
  } finally {
    if (active && version === generation) loading.value = false
  }
}
watch(
  () => [props.projectId, props.revision],
  () => void load(),
  { immediate: true },
)
function edit(entry: ContextEntry) {
  selected.value = entry
  Object.assign(draft, {
    content: entry.content,
    status: entry.status,
    reason: '',
    promote: false,
  })
  editError.value = ''
  editing.value = true
}
async function save() {
  if (saving.value || !selected.value) return
  if (!draft.reason.trim() || !draft.content.trim()) {
    editError.value = '内容和纠正原因不能为空'
    return
  }
  const entry = selected.value
  const data: UpdateEntry = {
    version: entry.version,
    reason: draft.reason.trim(),
    status: draft.status,
  }
  if (entry.kind !== 'term' && draft.content !== entry.content)
    data.content = draft.content.trim()
  if (draft.promote) data.kind = 'long_memory'
  saving.value = true
  editError.value = ''
  try {
    const result = await updateEntry(entry.id, data)
    if (active) {
      snapshotFailed.value = !result.snapshot.published
      notice.value = result.snapshot.published
        ? '纠正内容已保存，快照已发布'
        : '纠正内容已保存，但快照发布失败，请重发快照'
      editing.value = false
      await load()
    }
  } catch (e) {
    if (active)
      editError.value =
        errorMessage(e) +
        '；版本冲突或结果不明时，请取消并刷新后核对条目，再重新纠正。'
  } finally {
    if (active) saving.value = false
  }
}
async function publish() {
  if (publishing.value || saving.value || props.disabled) return
  publishing.value = true
  error.value = ''
  try {
    const result = await publishEntries(props.projectId)
    if (active) {
      snapshotFailed.value = Object.values(result).some((s) => !s.published)
      notice.value = snapshotFailed.value
        ? '部分快照仍未发布，请检查服务后重试'
        : '上下文快照已发布'
    }
  } catch (e) {
    if (active) error.value = errorMessage(e)
  } finally {
    if (active) publishing.value = false
  }
}
</script>
<style scoped>
.context-panel {
  display: grid;
  gap: 20px;
}
h2 {
  margin: 0;
  font-size: 20px;
}
.entry-card {
  padding: 18px 0;
  border-top: 1px solid var(--pm-border);
}
.entry-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--pm-text-secondary);
}
.entry-meta .n-button {
  margin-left: auto;
}
.entry-card p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.8;
}
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
