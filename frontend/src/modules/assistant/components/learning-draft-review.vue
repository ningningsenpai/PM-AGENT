<template>
  <n-drawer :show="show" :width="780" :mask-closable="!busy" :close-on-esc="!busy" @update:show="emit('update:show', $event)">
    <n-drawer-content title="核对学习结果" :closable="!busy">
      <div class="review-intro">
        <n-space align="center"><n-tag :type="draft.state === 'applied' ? 'success' : 'info'">{{ draftStates[draft.state] }}</n-tag><span class="muted">草稿版本 {{ draft.version }}</span></n-space>
        <p>{{ draftSummary(draft) }}</p>
        <p class="muted">请核对内容、来源和适用条件。只有确认发布的条目才会参与后续问答；人工编辑不调用模型。</p>
      </div>
      <RequestError :message="error" />
      <RequestError :message="operation.error.value" />
      <n-alert v-if="operation.run.value?.operation === 'learn_refine' && operation.run.value.status === 'failed'" type="warning">整理失败：{{ operation.run.value.error }}。反馈已保留，可核对后重新整理。</n-alert>
      <n-alert v-if="draft.conflicts.length" type="warning" title="发现需要核对的关系">
        <p v-for="(conflict, index) in draft.conflicts" :key="index">{{ conflict.left }} ↔ {{ conflict.right }}</p>
        可以说明不同的适用条件，或取消其中一项。是否共存需要你明确确认。
      </n-alert>
      <n-alert v-for="(publication, scope) in draft.publications" :key="scope" :type="publication.published ? 'success' : 'warning'">
        {{ targetFileLabel(String(scope)) }}：{{ publication.published ? '已更新并生效' : publication.error || '等待恢复' }}
      </n-alert>
      <n-space v-if="editable" class="selection-tools">
        <n-button size="small" :disabled="busy" @click="selectedIds = candidates.map(c => c.id)">全选</n-button>
        <n-button size="small" :disabled="busy" @click="selectedIds = []">清空选择</n-button>
        <n-button size="small" :disabled="busy || dirty || !selectedIds.length" @click="showFeedback = true">反馈整理所选内容</n-button>
        <span class="muted">已选 {{ selectedIds.length }} 条</span>
      </n-space>
      <n-empty v-if="!candidates.length" description="本轮没有提取到可复用内容" />
      <article v-for="(candidate, index) in candidates" :key="candidate.id" class="review-candidate">
        <div class="candidate-head">
          <n-checkbox :checked="selectedIds.includes(candidate.id)" :disabled="!editable || busy" @update:checked="toggle(candidate.id, $event)">{{ entryKinds[candidate.proposal.kind] }} · {{ candidate.proposal.scope === 'user' ? '个人通用' : '当前项目' }}</n-checkbox>
          <n-tag v-if="candidate.proposal.invalidate" size="small" type="warning">失效原条目</n-tag>
          <n-tag v-else size="small">{{ candidate.proposal.replacesEntryId ? '修改已有内容' : '新增内容' }}</n-tag>
        </div>
        <p class="candidate-content">{{ candidate.proposal.content }}</p>
        <p v-if="candidate.proposal.conditions.length" class="muted">适用条件：{{ candidate.proposal.conditions.join('；') }}</p>
        <p v-if="previous(candidate)" class="previous-content">原内容：{{ previous(candidate) }}</p>
        <details>
          <summary>{{ editable ? '编辑与来源' : '查看内容与来源' }}</summary>
          <LearningCandidateEditor v-model="candidates[index]!" :existing="draft.existing" :candidates="candidates" :disabled="!editable || busy" />
        </details>
      </article>
      <n-form-item v-if="dirty" label="本次修改说明"><n-input v-model:value="editReason" :maxlength="1000" placeholder="说明你调整了什么" /></n-form-item>
      <details v-if="draft.feedback.length" class="history">
        <summary>用户反馈（{{ draft.feedback.length }}）</summary>
        <blockquote v-for="feedback in draft.feedback" :key="feedback.id">{{ feedback.text }}</blockquote>
      </details>
      <details v-if="draft.history.length" class="history">
        <summary>草稿历史与修改前内容</summary>
        <div v-for="(history, index) in draft.history" :key="index"><b>版本 {{ history.version }} · {{ history.reason }}</b><ul><li v-for="item in history.candidates" :key="item.id">{{ item.proposal.content }}<span v-if="item.proposal.conditions.length">（{{ item.proposal.conditions.join('；') }}）</span></li></ul></div>
      </details>
      <small class="muted">草稿编号 {{ draft.id }} · {{ formatDate(draft.createdAt) }}</small>
      <template #footer>
        <n-space justify="end">
          <n-button :disabled="busy" @click="refresh">重新读取</n-button>
          <n-button v-if="editable || draft.state === 'partial' || draft.replacementDraftId" :disabled="busy || dirty" @click="rebase">{{ draft.replacementDraftId ? '查看后继草稿' : draft.state === 'partial' ? '重新核对未发布内容' : '核对最新正式内容' }}</n-button>
          <n-button v-if="dirty" type="primary" :loading="saving" :disabled="busy || !editReason.trim()" @click="save">保存草稿</n-button>
          <n-button v-else-if="editable" type="primary" :loading="saving" :disabled="busy" @click="confirm">{{ selectedIds.length ? `确认发布 ${selectedIds.length} 条` : '不采纳本次候选' }}</n-button>
          <n-button v-else-if="['partial', 'updating'].includes(draft.state) && !draft.replacementDraftId" type="primary" :loading="saving" :disabled="busy" @click="confirm">恢复原更新</n-button>
        </n-space>
      </template>
    </n-drawer-content>
  </n-drawer>
  <n-modal v-model:show="showFeedback" preset="card" title="解释所选内容的含义" style="width: 590px" :closable="!busy" :mask-closable="!busy">
    <p class="muted">将只整理已选 {{ selectedIds.length }} 条候选。你可以解释冲突、区分适用条件，或要求拆分、合并。整理会调用模型，结果仍需你确认。</p>
    <n-input v-model:value="feedback" type="textarea" :maxlength="4000" :autosize="{ minRows: 5, maxRows: 10 }" placeholder="例如：中文适用于日常讨论，英文只用于对外报告。这两条请分别保留。" :disabled="busy" />
    <template #footer><n-space justify="end"><n-button :disabled="busy" @click="showFeedback = false">取消</n-button><n-button type="primary" :disabled="busy || !feedback.trim()" :loading="operation.busy.value" @click="refine">提交反馈并整理</n-button></n-space></template>
  </n-modal>
</template>
<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { confirmDraft, editDraft, getDraft, rebaseDraft } from '../api'
import { draftStates, draftSummary, entryKinds, reconcileSelection } from '../learning'
import type { DraftCandidate, LearningDraft } from '../types'
import type { useOperation } from '../operation'
import { errorMessage, formatDate } from '@/shared/utils/format'
import RequestError from '@/shared/components/request-error.vue'
import LearningCandidateEditor from './learning-candidate-editor.vue'
const props = defineProps<{ draft: LearningDraft; show: boolean; operation: ReturnType<typeof useOperation>; disabled?: boolean }>()
const emit = defineEmits<{ 'update:show': [value: boolean]; updated: [draft: LearningDraft]; busy: [value: boolean] }>()
const candidates = ref<DraftCandidate[]>([])
const selectedIds = ref<string[]>([])
const saving = ref(false)
const error = ref('')
const editReason = ref('')
const feedback = ref('')
const showFeedback = ref(false)
const editable = computed(() => props.draft.state === 'pending' && !props.draft.plan)
const dirty = computed(() => JSON.stringify(candidates.value) !== JSON.stringify(props.draft.candidates))
const busy = computed(() => saving.value || props.operation.busy.value || props.operation.unresolved.value || !!props.disabled)
let active = true
onScopeDispose(() => { active = false; emit('busy', false) })
watch(saving, value => emit('busy', value), { flush: 'sync' })
watch(() => [props.draft.id, props.draft.version, props.draft.state], () => {
  selectedIds.value = props.draft.plan?.candidateIds || reconcileSelection(candidates.value.map(c => c.id), props.draft.candidates.map(c => c.id), selectedIds.value)
  candidates.value = JSON.parse(JSON.stringify(props.draft.candidates))
  editReason.value = ''
}, { immediate: true })
function toggle(id: string, checked: boolean) {
  selectedIds.value = checked ? [...new Set([...selectedIds.value, id])] : selectedIds.value.filter(value => value !== id)
}
function previous(candidate: DraftCandidate) {
  return props.draft.existing.find(e => e.id === candidate.proposal.replacesEntryId)?.content
}
async function perform(action: () => Promise<LearningDraft>) {
  if (saving.value) return
  saving.value = true
  error.value = ''
  try { const value = await action(); if (active) emit('updated', value) }
  catch (e) { if (active) error.value = errorMessage(e) + '；结果不明时先重新读取，固定文件更新可按原计划恢复。' }
  finally { if (active) saving.value = false }
}
function refresh() { return perform(() => getDraft(props.draft.projectId, props.draft.id)) }
function save() { return perform(() => editDraft(props.draft.projectId, props.draft.id, props.draft.version, candidates.value, editReason.value.trim())) }
function rebase() { return perform(() => rebaseDraft(props.draft.projectId, props.draft.id, props.draft.version)) }
function confirm() {
  const plan = props.draft.plan
  return perform(() => confirmDraft(props.draft.projectId, props.draft.id, plan?.version || props.draft.version, plan?.candidateIds || selectedIds.value))
}
function targetFileLabel(path: string) {
  return ({
    'project_specification.json': '项目规则文件',
    'short_term_memory.json': '短期记忆文件',
    'long_term_memory.json': '长期记忆文件',
    'user_habits/work.json': '工作习惯文件',
    'user_habits/thinking.json': '思考习惯文件',
    'user_habits/specification.json': '规范习惯文件',
    'user_habits/tooling.json': '工具习惯文件',
    'user_habits/life.json': '生活习惯文件',
  } as Record<string, string>)[path] || path
}
async function refine() {
  if (busy.value || !feedback.value.trim()) return
  showFeedback.value = false
  await props.operation.start('learn_refine', { draftId: props.draft.id, version: props.draft.version, candidateIds: selectedIds.value, feedback: feedback.value.trim() })
  if (active) { feedback.value = ''; await refresh() }
}
</script>
<style scoped>
.review-intro { margin-bottom: 20px; }
.selection-tools { margin: 20px 0; }
.review-candidate { padding: 20px 0; border-top: 1px solid var(--pm-border); }
.candidate-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.candidate-content { white-space: pre-wrap; line-height: 1.7; overflow-wrap: anywhere; }
.previous-content { padding: 10px 12px; border-radius: 8px; background: var(--pm-bg); color: var(--pm-text-secondary); }
.history { margin: 20px 0; }
summary { cursor: pointer; color: var(--pm-text-secondary); }
blockquote { margin: 10px 0; padding: 12px; background: var(--pm-bg); white-space: pre-wrap; }
.n-alert { margin-bottom: 12px; }
</style>
