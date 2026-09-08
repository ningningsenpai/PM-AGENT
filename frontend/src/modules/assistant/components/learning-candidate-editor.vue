<template>
  <div class="candidate-editor">
    <n-form label-placement="top" :disabled="disabled">
      <div class="two-columns">
        <n-form-item label="内容分类"><n-select v-model:value="proposal.kind" :options="kindOptions" @update:value="validateScope" /></n-form-item>
        <n-form-item label="适用范围"><n-select v-model:value="proposal.scope" :options="scopeOptions" /></n-form-item>
      </div>
      <n-form-item label="主题"><n-input v-model:value="proposal.key" :maxlength="200" /></n-form-item>
      <n-form-item label="内容"><n-input v-model:value="proposal.content" type="textarea" :maxlength="4000" :autosize="{ minRows: 2, maxRows: 8 }" /></n-form-item>
      <n-form-item label="适用条件（每行一项）"><n-input :value="proposal.conditions.join('\n')" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="例如：日常讨论、对外英文报告" @update:value="proposal.conditions = splitLines($event)" /></n-form-item>
      <div v-if="proposal.kind === 'term'" class="two-columns">
        <n-form-item label="标准词"><n-input v-model:value="proposal.canonical" :maxlength="200" /></n-form-item>
        <n-form-item label="别名（每行一个）"><n-input :value="proposal.aliases.join('\n')" type="textarea" @update:value="proposal.aliases = splitLines($event)" /></n-form-item>
      </div>
      <n-form-item label="替换已有内容（留空表示新建）"><n-select v-model:value="proposal.replacesEntryId" clearable :options="replacementOptions" /></n-form-item>
      <n-checkbox v-model:checked="proposal.invalidate" :disabled="disabled || !proposal.replacesEntryId">将关联的原条目标记为失效</n-checkbox>
      <details class="relations">
        <summary>拆分与共存关系</summary>
        <p class="muted">如果两条内容适用于不同场景，请为它们分别补充条件，并明确关联及共存理由。同条件下的矛盾不能直接并存。</p>
        <n-form-item label="关联条目"><n-select v-model:value="proposal.relatedEntryIds" multiple :options="relationOptions" /></n-form-item>
        <n-form-item label="共存理由"><n-input v-model:value="proposal.coexistReason" type="textarea" :maxlength="1000" /></n-form-item>
      </details>
    </n-form>
    <details>
      <summary>核对来源</summary>
      <blockquote>{{ proposal.sourceQuote }}</blockquote>
      <small class="muted">来源编号 {{ proposal.sourceMessageId }}</small>
    </details>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { entryKinds, splitLines } from '../learning'
import type { ContextEntry, DraftCandidate } from '../types'
const model = defineModel<DraftCandidate>({ required: true })
const props = defineProps<{ existing: ContextEntry[]; candidates: DraftCandidate[]; disabled: boolean }>()
const proposal = computed(() => model.value.proposal)
const kindOptions = Object.entries(entryKinds).map(([value, label]) => ({ value, label }))
const scopeOptions = computed(() => [{ label: '当前项目', value: 'project' },
  ...(['habit', 'term'].includes(proposal.value.kind) ? [{ label: '个人通用（跨项目）', value: 'user' }] : [])])
const replacementOptions = computed(() => props.existing.filter(e => e.kind === proposal.value.kind && (proposal.value.scope === 'user' ? !e.projectId : !!e.projectId))
  .map(e => ({ label: `${e.content.slice(0, 80)} · v${e.version}`, value: e.id })))
const relationOptions = computed(() => [
  ...props.existing.map(e => ({ label: `已有：${e.content.slice(0, 70)}`, value: e.id })),
  ...props.candidates.filter(c => c.id !== model.value.id).map(c => ({ label: `候选：${c.proposal.content.slice(0, 70)}`, value: c.id })),
])
function validateScope() {
  if (!['habit', 'term'].includes(proposal.value.kind)) proposal.value.scope = 'project'
  proposal.value.replacesEntryId = null
  proposal.value.invalidate = false
}
</script>
<style scoped>
.two-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.relations { margin: 16px 0; }
summary { cursor: pointer; color: var(--pm-text-secondary); }
blockquote { margin: 12px 0; padding: 12px; background: var(--pm-bg); border-left: 3px solid var(--pm-border); white-space: pre-wrap; }
.candidate-editor { padding: 12px 0; }
</style>
