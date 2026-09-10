<template>
  <section class="surface padded file-panel">
    <div class="page-title-row">
      <div>
        <h2>项目文件与解析</h2>
        <p class="muted">
          同步文件后，解析内容供 PM 助手检索；解析不会生成任务。
        </p>
      </div>
      <n-space
        ><n-button :loading="loading" :disabled="busy || disabled" @click="refresh"
          >刷新列表</n-button
        ><n-button
          :disabled="busy || hasPending || showParse || loading || disabled || !selected.length"
          @click="parse(true)"
          >重试所选（{{ selected.length }}）</n-button
        ><n-button
          type="primary"
          :loading="busy"
          :disabled="busy || hasPending || showParse || loading || disabled || !files.length"
          @click="parse(false)"
          >解析项目文件</n-button
        ></n-space
      >
    </div>
    <RequestError :message="error" />
    <n-alert
      v-if="hasPending && !busy"
      :type="recovering ? 'info' : 'warning'"
      :title="recovering ? '正在确认上次解析批次' : '存在待确认的解析批次'"
    >
      {{ recovering
        ? '后端仍在处理时每 5 秒确认一次；可以离开本页，返回后会自动恢复。'
        : (parseError || '上一次解析请求的结果尚未确认，请使用原幂等键恢复，避免重复调用模型。') }}
      <p v-if="pendingStartedAt" class="muted">发起时间：{{ formatDate(pendingStartedAt) }}</p>
      <p v-if="leaseUntil" class="muted">当前租约截止：{{ formatDate(leaseUntil) }}</p>
      <template #action>
        <n-button size="small" :loading="recovering" :disabled="recovering || loading" @click="resumeParsing">
          {{ recovering ? '正在自动确认' : '重新确认' }}
        </n-button>
      </template>
    </n-alert>
    <n-alert
      v-if="phase === 'error' && parseError && !hasPending && !showParse"
      type="error"
      title="解析未成功"
    >
      {{ parseError }}
      <template #action>
        <n-button size="small" type="warning" :disabled="busy || disabled" @click="retryRecoveredParsing">
          立即重试
        </n-button>
      </template>
    </n-alert>
    <n-alert v-if="busy" type="info"
      >正在解析，请保持页面打开。模型处理可能需要数分钟，完成后会更新结果。</n-alert
    >
    <n-alert
      v-if="result"
      :type="
        result.status === 'partial' ||
        result.indexStatus === 'failed' ||
        result.specificationStatus === 'failed'
          ? 'warning'
          : 'success'
      "
      title="解析结果"
    >
      本轮候选 {{ result.candidateCount }} 个，成功
      {{ result.successCount }} 个，失败 {{ result.failureCount }} 个。
      项目规范：{{
        { updated: '已更新', kept: '保持原有内容', failed: '更新失败' }[
          result.specificationStatus
        ]
      }}； 文件索引：{{
        result.indexStatus === 'updated' ? '已更新' : '发布失败'
      }}。
      <p v-if="result.runId" class="muted">运行编号：{{ result.runId }}</p>
      <ul v-if="result.failures.length">
        <li v-for="failure in result.failures" :key="failure.fileId">
          {{ failure.relativePath }}：{{ failure.errorMessage }}（{{
            failure.errorCode
          }}）
        </li>
      </ul>
    </n-alert>
    <div class="toolbar">
      <n-input
        v-model:value="query"
        clearable
        placeholder="查找文件路径"
        style="max-width: 320px"
      /><n-select
        v-model:value="status"
        :options="statuses"
        style="width: 180px"
      /><span class="muted">{{ files.length }} 个文件</span>
    </div>
    <n-data-table
      :columns="columns"
      :data="filtered"
      :row-key="(row: ProjectFileResponse) => row.id"
      :checked-row-keys="selected"
      @update:checked-row-keys="
        (keys: Array<string | number>) => (selected = keys as number[])
      "
      :loading="loading"
      :pagination="{ pageSize: 10 }"
      :scroll-x="850"
    />
    <n-modal
      v-model:show="showParse"
      preset="card"
      :title="parseIds ? '重新解析所选文件' : '解析项目文件'"
      :closable="!busy"
      :mask-closable="false"
      :close-on-esc="!busy"
      style="width: 560px"
    >
      <p>{{ parseIds ? '将重新解析所选文件，可能产生模型调用费用。' : '将解析待处理文件并更新项目上下文，可能产生模型调用费用。' }}</p>
      <div v-if="phase !== 'idle'" class="parse-progress" aria-live="polite">
        <div class="parse-progress-heading">
          <strong>{{ parseStage }}</strong>
          <span>{{ completed }} / {{ total }} 个文件</span>
        </div>
        <n-progress type="line" :percentage="percentage" :status="progressStatus" aria-label="本轮文件解析进度">{{ percentage }}%</n-progress>
        <p class="muted">按本轮已处理文件数更新，包含成功和失败文件；规范与索引更新完成后才结束本次解析。</p>
        <n-alert v-if="result" :type="parseHasFailures ? 'warning' : 'success'">
          成功 {{ result.successCount }} 个，失败 {{ result.failureCount }} 个。
          {{ parseHasFailures ? '本轮存在解析或发布失败，请查看页面解析结果。' : '项目规范与文件索引已处理完成。' }}
        </n-alert>
        <RequestError :message="parseError" />
        <n-alert v-if="progressError" type="warning">{{ progressError }}</n-alert>
      </div>
      <template #footer>
        <n-space justify="end">
          <n-button :disabled="busy" @click="showParse = false">{{ phase === 'idle' ? '取消' : '关闭' }}</n-button>
          <n-button v-if="phase === 'error' && !hasPending" type="warning" :loading="busy" :disabled="busy || disabled" @click="retryParsing">立即重试</n-button>
          <n-button type="primary" :loading="busy" :disabled="busy || disabled || phase !== 'idle'" @click="startParsing">开始解析</n-button>
        </n-space>
      </template>
    </n-modal>
    <n-modal
      v-model:show="showRead"
      preset="card"
      title="读取原始文件"
      style="width: 620px"
    >
      <p>
        原始文件可能包含不可信内容。仅在确认来源后打开，临时链接到期后需重新获取。
      </p>
      <a
        v-if="readUrl"
        :href="readUrl"
        target="_blank"
        rel="noopener noreferrer"
        >在新标签页读取 {{ readName }}</a
      >
    </n-modal>
  </section>
</template>
<script setup lang="ts">
import { computed, h, onScopeDispose, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import {
  NButton,
  NTag,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'
import {
  getFileReadUrl,
  listProjectFiles,
} from '../api'
import type { ProjectFileResponse } from '../types'
import { useFileParsing } from '../file-parsing'
import RequestError from '@/shared/components/request-error.vue'
import { errorMessage, formatDate } from '@/shared/utils/format'
const props = defineProps<{
  projectId: string
  revision?: number
  disabled?: boolean
}>()
const emit = defineEmits<{ busy: [value: boolean] }>()
const files = ref<ProjectFileResponse[]>([])
const selected = ref<number[]>([])
const query = ref('')
const status = ref('all')
const loading = ref(false)
const error = ref('')
const showParse = ref(false)
const parseIds = ref<number[]>()
const parsing = useFileParsing(props.projectId, updateFiles)
const {
  busy,
  recovering,
  phase,
  total,
  completed,
  percentage,
  result,
  error: parseError,
  progressError,
  hasPending,
  pendingFileIds,
  pendingStartedAt,
  retryFileIds,
  leaseUntil,
  recover,
  recoverOnce,
} = parsing
const parseHasFailures = computed(() => Boolean(result.value && (result.value.status === 'partial'
  || result.value.failureCount || result.value.indexStatus === 'failed' || result.value.specificationStatus === 'failed')))
const progressStatus = computed(() => phase.value === 'error' ? 'error'
  : phase.value === 'finished' ? parseHasFailures.value ? 'warning' : 'success' : 'default')
const parseStage = computed(() => ({
  idle: '待开始',
  preparing: '正在读取待解析文件',
  parsing: '正在解析文件',
  publishing: '正在等待项目规范与索引更新',
  finished: parseHasFailures.value ? '解析结束，部分未成功' : '解析完成',
  error: hasPending.value ? '恢复已暂停，可稍后重新确认' : '解析未成功，可立即重试',
})[phase.value])
const showRead = ref(false)
const readUrl = ref('')
const readName = ref('')
const message = useMessage()
let generation = 0
let active = true
onScopeDispose(() => {
  active = false
  generation++
})
watch(
  () => busy.value,
  (value) => emit('busy', value),
  { flush: 'sync', immediate: true },
)
watch(
  () => recovering.value,
  (value, previous) => {
    if (previous && !value && active) void load()
  },
)
function guard() {
  if (busy.value) {
    message.warning('正在解析文件，请等待操作结束')
    return false
  }
}
onBeforeRouteLeave(guard)
onBeforeRouteUpdate(guard)
const labels: Record<string, string> = {
  pending: '待解析',
  success: '解析成功',
  failed: '解析失败',
  unavailable: '不可用',
}
const statuses = [
  { label: '全部解析状态', value: 'all' },
  ...Object.entries(labels).map(([value, label]) => ({ value, label })),
]
const filtered = computed(() =>
  files.value.filter(
    (f) =>
      f.relativePath.toLowerCase().includes(query.value.trim().toLowerCase()) &&
      (status.value === 'all' || f.analysisStatus === status.value),
  ),
)
const columns: DataTableColumns<ProjectFileResponse> = [
  { type: 'selection', disabled: () => busy.value || Boolean(props.disabled) },
  {
    title: '文件路径',
    key: 'relativePath',
    minWidth: 240,
    render: (row) =>
      h('div', [
        h('strong', row.relativePath),
        row.lastErrorMessage
          ? h(
              'p',
              { class: 'file-error' },
              row.lastErrorMessage +
                (row.lastErrorCode ? '（' + row.lastErrorCode + '）' : ''),
            )
          : null,
      ]),
  },
  {
    title: '大小',
    key: 'sizeBytes',
    width: 95,
    render: (row) =>
      row.sizeBytes < 1024
        ? row.sizeBytes + ' B'
        : (row.sizeBytes / 1024).toFixed(1) + ' KB',
  },
  {
    title: '解析状态',
    key: 'analysisStatus',
    width: 110,
    render: (row) =>
      h(
        NTag,
        {
          size: 'small',
          type:
            row.analysisStatus === 'success'
              ? 'success'
              : row.analysisStatus === 'failed'
                ? 'error'
                : 'default',
        },
        () => labels[row.analysisStatus] || row.analysisStatus,
      ),
  },
  { title: '尝试次数', key: 'parseAttempts', width: 90 },
  {
    title: '操作',
    key: 'action',
    width: 120,
    render: (row) =>
      h(NButton, { size: 'small', onClick: () => read(row) }, () => '读取原文'),
  },
]
async function load() {
  const current = ++generation
  loading.value = true
  error.value = ''
  try {
    const data = await listProjectFiles(props.projectId)
    if (active && current === generation) {
      updateFiles(data)
    }
  } catch (e) {
    if (active && current === generation) error.value = errorMessage(e)
  } finally {
    if (active && current === generation) loading.value = false
  }
}
async function refresh() {
  if (busy.value || loading.value || props.disabled) return
  if (hasPending.value && !recovering.value) {
    await recoverOnce()
  }
  if (active) await load()
}
function updateFiles(data: ProjectFileResponse[]) {
  files.value = data
  selected.value = selected.value.filter((id) => data.some((file) => file.id === id))
}
watch(
  () => [props.projectId, props.revision],
  () => void load(),
  { immediate: true },
)
function parse(targeted: boolean) {
  if (busy.value || showParse.value || loading.value || props.disabled) return
  if (targeted && !selected.value.length) return
  if (targeted && selected.value.length > 100) {
    message.warning('一次最多重试 100 个文件')
    return
  }
  if (!parsing.reset()) return
  parseIds.value = targeted ? [...selected.value] : undefined
  showParse.value = true
}
async function resumeParsing() {
  if (busy.value || recovering.value || showParse.value || loading.value || props.disabled) return
  if (!parsing.reset()) return
  parseIds.value = pendingFileIds.value ? [...pendingFileIds.value] : undefined
  showParse.value = true
  await recover()
  if (!active) return
  await load()
  if (parseError.value) error.value = parseError.value
}
async function retryRecoveredParsing() {
  if (busy.value || recovering.value || hasPending.value || props.disabled) return
  if (!parsing.reset()) return
  parseIds.value = retryFileIds.value ? [...retryFileIds.value] : undefined
  showParse.value = true
  await startParsing()
}
async function startParsing() {
  if (!showParse.value || busy.value || props.disabled || phase.value !== 'idle') return
  error.value = ''
  await parsing.start(parseIds.value)
  if (!active) return
  await load()
  if (parseError.value) error.value = parseError.value
}
async function retryParsing() {
  if (busy.value || hasPending.value || props.disabled) return
  if (!parsing.reset()) return
  await startParsing()
}
async function read(file: ProjectFileResponse) {
  try {
    const data = await getFileReadUrl(props.projectId, file.id)
    const url = new URL(data.url)
    if (!['https:', 'http:'].includes(url.protocol))
      throw new Error('文件链接格式不受支持')
    if (active) {
      readUrl.value = url.href
      readName.value = file.fileName
      showRead.value = true
    }
  } catch (e) {
    if (active) error.value = errorMessage(e)
  }
}
</script>
<style scoped>
.file-panel {
  display: grid;
  gap: 18px;
}
h2 {
  margin: 0;
}
.parse-progress {
  display: grid;
  gap: 16px;
  margin-top: 24px;
}
.parse-progress-heading {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}
.parse-progress-heading span {
  color: var(--pm-text-secondary);
}
.parse-progress p {
  margin: 0;
  line-height: 1.7;
}
:deep(.file-error) {
  color: #b54708;
  font-size: 12px;
  overflow-wrap: anywhere;
}
</style>
