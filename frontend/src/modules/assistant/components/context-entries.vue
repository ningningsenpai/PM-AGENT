<template>
  <section class="context-panel">
    <div class="page-title-row">
      <div><h2>已学习内容</h2><p class="muted">管理已发布的习惯、规则与记忆。个人通用内容在你的项目间共享，草稿需在会话中确认后生效。</p></div>
      <n-button :loading="loading" :disabled="saving" @click="load">刷新内容</n-button>
    </div>
    <RequestError :message="error" />
    <n-alert v-if="notice" type="success">{{ notice }}</n-alert>
    <n-alert v-if="pending" type="warning">有一项纠正尚未确认结果。请恢复原保存，或刷新内容核对。<n-button size="small" :loading="saving" @click="submitPending">恢复原保存</n-button></n-alert>
    <n-tabs v-model:value="category" type="line"><n-tab name="all">全部 {{ entries.length }}</n-tab><n-tab v-for="(label, kind) in entryKinds" :key="kind" :name="kind">{{ label }} {{ entries.filter(e => e.kind === kind).length }}</n-tab></n-tabs>
    <div class="toolbar">
      <n-input v-model:value="query" placeholder="查找内容或主题" clearable style="max-width: 320px" />
      <n-select v-model:value="filter" :options="[{ label: '全部状态', value: 'all' }, ...statuses, { label: '已过期', value: 'expired' }]" style="width: 160px" />
      <span class="muted">{{ filtered.length }} 条</span>
    </div>
    <n-spin :show="loading">
      <n-empty v-if="!filtered.length && !loading && !error" description="暂无符合条件的内容。可在会话中点击“学习本会话”，核对结果后发布。" />
      <article v-for="entry in filtered" :key="entry.id" class="entry-card">
        <div class="entry-meta"><n-tag size="small" :type="entryState(entry) === 'active' ? 'success' : 'default'">{{ stateLabels[entryState(entry)] }}</n-tag><span>{{ entryKinds[entry.kind] }} · {{ entry.projectId ? '当前项目' : '个人通用' }} · 版本 {{ entry.version }}</span><n-button size="small" :disabled="saving || disabled || !!pending" @click="edit(entry)">查看与纠正</n-button></div>
        <p>{{ entry.content }}</p>
        <p v-if="entry.conditions.length" class="muted">适用条件：{{ entry.conditions.join('；') }}</p>
        <small class="muted">{{ sourceLabel(entry) }}<template v-if="entry.expiresAt"> · 到期 {{ formatDate(entry.expiresAt) }}</template></small>
      </article>
    </n-spin>
    <n-modal v-model:show="editing" preset="card" title="查看与纠正内容" style="width: 720px" :mask-closable="!saving" :close-on-esc="!saving" :closable="!saving">
      <template v-if="selected">
        <n-alert type="info">直接编辑不会调用模型。保存后生成新的正式版本；原内容和修改原因保留在历史中。</n-alert>
        <n-form label-placement="top" :disabled="saving || !!pending">
          <n-form-item label="内容"><n-input v-model:value="draft.content" type="textarea" :maxlength="4000" :autosize="{ minRows: 3, maxRows: 8 }" /></n-form-item>
          <n-form-item label="适用条件（每行一项）"><n-input v-model:value="draft.conditions" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" /></n-form-item>
          <template v-if="selected.kind === 'term'"><n-form-item label="标准词"><n-input v-model:value="draft.canonical" :maxlength="200" /></n-form-item><n-form-item label="别名（每行一个）"><n-input v-model:value="draft.aliases" type="textarea" /></n-form-item></template>
          <n-form-item label="状态"><n-select v-model:value="draft.status" :options="statuses" /></n-form-item>
          <n-form-item label="到期时间（留空表示不设置期限）"><input v-model="draft.expiresAt" class="date-input" type="datetime-local" :disabled="saving || !!pending || draft.promote" /></n-form-item>
          <n-checkbox v-if="selected.kind === 'short_memory'" v-model:checked="draft.promote">确认为长期记忆并取消到期时间</n-checkbox>
          <n-form-item label="纠正原因（必填）"><n-input v-model:value="draft.reason" :maxlength="1000" placeholder="说明为什么需要调整这条内容" /></n-form-item>
        </n-form>
        <details open><summary>来源</summary><blockquote v-if="selected.attributes.sourceQuote">{{ selected.attributes.sourceQuote }}</blockquote><p class="muted">{{ sourceLabel(selected) }}</p><p v-if="selected.sourceMessageId" class="muted">来源消息 {{ selected.sourceMessageId }}</p><p v-if="selected.attributes.draftId" class="muted">学习草稿 {{ selected.attributes.draftId }} · 版本 {{ selected.attributes.draftVersion }}</p><details><summary>完整来源信息</summary><pre>{{ JSON.stringify(selected.attributes, null, 2) }}</pre></details></details>
        <details class="history"><summary>修改历史（{{ history.length }}）</summary><RequestError :message="historyError" /><p v-if="historyLoading" class="muted">正在读取历史…</p><article v-for="(change, index) in history" :key="index" class="change"><b>{{ change.version ? `版本 ${change.version} · ` : '' }}{{ change.reason }}</b><p v-if="change.before?.content">修改前：{{ change.before.content }}</p><p v-if="change.after?.content">修改后：{{ change.after.content }}</p><p v-if="change.proposal?.content">文件候选：{{ change.proposal.content }}</p></article></details>
        <RequestError :message="editError" />
        <n-space justify="end"><n-button :disabled="saving" @click="editing = false">关闭</n-button><n-button :loading="saving" :disabled="saving || !!pending || disabled" type="primary" @click="save">保存纠正</n-button></n-space>
      </template>
    </n-modal>
  </section>
</template>
<script setup lang="ts">
import { computed, onScopeDispose, reactive, ref, watch } from 'vue'
import { listChanges, listEntries, updateEntry } from '../api'
import type { ContextChange, ContextEntry, EntryStatus, UpdateEntry } from '../types'
import { entryKinds, entryState, splitLines } from '../learning'
import RequestError from '@/shared/components/request-error.vue'
import { RequestError as ApiError } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { errorMessage, formatDate, serverDate } from '@/shared/utils/format'
const props = defineProps<{ projectId: string; revision?: number; disabled?: boolean }>()
const emit = defineEmits<{ busy: [value: boolean] }>()
const entries = ref<ContextEntry[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const editError = ref('')
const notice = ref('')
const query = ref('')
const filter = ref('all')
const category = ref('all')
const editing = ref(false)
const selected = ref<ContextEntry | null>(null)
const history = ref<ContextChange[]>([])
const historyError = ref('')
const historyLoading = ref(false)
const draft = reactive({ content: '', status: 'active' as EntryStatus, reason: '', promote: false, conditions: '', canonical: '', aliases: '', expiresAt: '' })
const pending = ref<{ entryId: string; data: UpdateEntry; key: string } | null>(null)
const userId = useAuthStore().user?.id
const token = useAuthStore().token
const storageKey = `pm-context-edit:${userId}:${props.projectId}`
let active = true
let generation = 0
const valid = () => active && useAuthStore().token === token
try { const stored = sessionStorage.getItem(storageKey); if (stored) { const value = JSON.parse(stored); if (value.data?.projectId === props.projectId && typeof value.key === 'string') pending.value = value } }
catch { error.value = '无法恢复上次保存记录，请刷新核对内容' }
onScopeDispose(() => { active = false; generation++ })
watch(saving, value => emit('busy', value), { flush: 'sync' })
const stateLabels: Record<string, string> = { active: '有效', pending: '待确认', invalid: '已失效', expired: '已过期' }
const statuses = [{ label: '有效', value: 'active' }, { label: '待确认', value: 'pending' }, { label: '已失效', value: 'invalid' }]
const filtered = computed(() => entries.value.filter(e =>
  (e.content + String(e.attributes.key || '')).includes(query.value.trim()) &&
  (category.value === 'all' || e.kind === category.value) && (filter.value === 'all' || entryState(e) === filter.value)))
function sourceLabel(entry: ContextEntry) {
  return ({ user_statement: '来自用户会话', user_feedback: '来自用户反馈', file_specification: '来自项目文件规范', legacy_cloud: '来自历史云端文件' } as Record<string, string>)[String(entry.attributes.sourceType)] || '历史学习内容'
}
async function load() {
  const version = ++generation
  loading.value = true
  error.value = ''
  try { const data = await listEntries(props.projectId); if (valid() && version === generation) entries.value = data }
  catch (e) { if (valid() && version === generation) error.value = errorMessage(e) }
  finally { if (valid() && version === generation) loading.value = false }
}
watch(() => [props.projectId, props.revision], () => void load(), { immediate: true })
function localDate(value: string | null) {
  if (!value) return ''
  const date = serverDate(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
async function edit(entry: ContextEntry) {
  selected.value = entry
  Object.assign(draft, { content: entry.content, status: entry.status, reason: '', promote: false, conditions: entry.conditions.join('\n'), canonical: String(entry.attributes.canonical || ''), aliases: Array.isArray(entry.attributes.aliases) ? entry.attributes.aliases.join('\n') : '', expiresAt: localDate(entry.expiresAt) })
  editError.value = ''
  editing.value = true
  history.value = []
  historyError.value = ''
  historyLoading.value = true
  try { const data = await listChanges(props.projectId, entry.id); if (valid() && selected.value?.id === entry.id) history.value = data }
  catch (e) { if (valid() && selected.value?.id === entry.id) historyError.value = errorMessage(e) }
  finally { if (valid() && selected.value?.id === entry.id) historyLoading.value = false }
}
async function save() {
  if (saving.value || pending.value || !selected.value || props.disabled) return
  if (!draft.reason.trim() || !draft.content.trim()) { editError.value = '内容和纠正原因不能为空'; return }
  if (selected.value.kind === 'term' && (!draft.canonical.trim() || !splitLines(draft.aliases).length)) { editError.value = '词条必须填写标准词和别名'; return }
  const data: UpdateEntry = { projectId: props.projectId, version: selected.value.version, reason: draft.reason.trim(), status: draft.status, content: draft.content.trim(), conditions: splitLines(draft.conditions), expiresAt: draft.promote || !draft.expiresAt ? null : new Date(draft.expiresAt).toISOString() }
  if (selected.value.kind === 'term') { data.canonical = draft.canonical.trim(); data.aliases = splitLines(draft.aliases) }
  if (draft.promote) data.kind = 'long_memory'
  const attempt = { entryId: selected.value.id, data, key: crypto.randomUUID() }
  try { sessionStorage.setItem(storageKey, JSON.stringify(attempt)); pending.value = attempt }
  catch { editError.value = '无法保存恢复信息，请检查浏览器存储权限后重试'; return }
  await submitPending()
}
async function submitPending() {
  if (saving.value || !pending.value || props.disabled) return
  saving.value = true
  editError.value = ''
  try {
    const result = await updateEntry(pending.value.entryId, pending.value.data, pending.value.key)
    if (valid()) {
      notice.value = `纠正已发布，内容版本 ${result.version}`
      pending.value = null
      sessionStorage.removeItem(storageKey)
      editing.value = false
      await load()
    }
  } catch (e) {
    if (valid()) {
      editError.value = errorMessage(e)
      error.value = errorMessage(e)
      if (e instanceof ApiError && !e.uncertain) { pending.value = null; sessionStorage.removeItem(storageKey) }
    }
  } finally { if (valid()) saving.value = false }
}
</script>
<style scoped>
.context-panel { display: grid; gap: 18px; }
h2 { margin: 0; font-size: 20px; }
.entry-card { padding: 18px 0; border-top: 1px solid var(--pm-border); }
.entry-meta { display: flex; align-items: center; gap: 12px; font-size: 12px; color: var(--pm-text-secondary); }
.entry-meta .n-button { margin-left: auto; }
.entry-card p { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.8; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 260px; overflow: auto; }
summary { cursor: pointer; color: var(--pm-text-secondary); }
.history { margin: 20px 0; }
.change { padding: 12px 0; border-bottom: 1px solid var(--pm-border); }
blockquote { background: var(--pm-bg); padding: 12px; margin: 12px 0; white-space: pre-wrap; }
.date-input { border: 1px solid var(--pm-border); padding: 8px 12px; border-radius: 6px; font: inherit; width: 100%; }
</style>
