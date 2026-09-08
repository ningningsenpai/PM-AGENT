<template>
  <section v-if="drafts.length || loading || error" class="learning-results">
    <div class="results-head"><h3>学习结果</h3><n-button text size="small" :loading="loading" @click="load">刷新结果</n-button></div>
    <RequestError :message="error" />
    <article v-for="draft in drafts" :key="draft.id" class="learning-result">
      <div class="result-heading"><n-tag size="small" :type="draft.state === 'published' ? 'success' : 'info'">{{ draftStates[draft.state] }}</n-tag><small>{{ formatDate(draft.createdAt) }}</small></div>
      <p>{{ draftSummary(draft) }}</p>
      <p v-if="draft.state === 'pending'" class="muted">候选尚未生效，请查看并选择要保留的内容。</p>
      <n-button secondary type="primary" size="small" @click="open(draft)">{{ draft.state === 'pending' ? '查看并确认' : '查看结果与历史' }}</n-button>
    </article>
    <LearningDraftReview v-if="selected" :key="selected.id" v-model:show="show" :draft="selected" :operation="operation" :disabled="disabled" @updated="updated" @busy="emit('busy', $event)" />
  </section>
</template>
<script setup lang="ts">
import { onMounted, onScopeDispose, ref, watch } from 'vue'
import { listDrafts } from '../api'
import { draftStates, draftSummary } from '../learning'
import type { LearningDraft } from '../types'
import type { useOperation } from '../operation'
import { errorMessage, formatDate } from '@/shared/utils/format'
import RequestError from '@/shared/components/request-error.vue'
import LearningDraftReview from './learning-draft-review.vue'
const props = defineProps<{ projectId: string; conversationId: string; operation: ReturnType<typeof useOperation>; disabled?: boolean }>()
const emit = defineEmits<{ changed: []; busy: [value: boolean] }>()
const drafts = ref<LearningDraft[]>([])
const selected = ref<LearningDraft | null>(null)
const show = ref(false)
const loading = ref(false)
const error = ref('')
let active = true
let generation = 0
onScopeDispose(() => { active = false; generation++ })
async function load() {
  const version = ++generation
  loading.value = true
  error.value = ''
  try {
    const values = await listDrafts(props.projectId, props.conversationId)
    if (!active || version !== generation) return
    drafts.value = values
    if (selected.value) selected.value = values.find(d => d.id === selected.value?.id) || selected.value
  } catch (e) { if (active && version === generation) error.value = errorMessage(e) }
  finally { if (active && version === generation) loading.value = false }
}
function open(draft: LearningDraft) { selected.value = draft; show.value = true }
function updated(draft: LearningDraft) {
  selected.value = draft
  const exists = drafts.value.some(value => value.id === draft.id)
  drafts.value = exists ? drafts.value.map(value => value.id === draft.id ? draft : value) : [draft, ...drafts.value]
  emit('changed')
}
watch(() => props.operation.run.value, async run => {
  if (!run || !['learn', 'learn_refine'].includes(run.operation) || run.status === 'running') return
  await load()
  if (active && run.operation === 'learn' && run.status === 'success') {
    const found = drafts.value.find(d => d.id === run.result.draftId)
    if (found) open(found)
  }
})
onMounted(load)
</script>
<style scoped>
.learning-results { display: grid; gap: 12px; }
.results-head, .result-heading { display: flex; align-items: center; gap: 12px; }
.results-head { justify-content: space-between; }
h3 { margin: 0; font-size: 15px; }
.learning-result { padding: 16px; background: var(--pm-green-soft); border: 1px solid var(--pm-border); border-radius: 12px; }
.result-heading small { color: var(--pm-text-secondary); }
.learning-result p { font-size: 13px; }
</style>
