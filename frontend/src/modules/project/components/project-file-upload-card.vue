<template>
  <n-card class="glass-card upload-card" :bordered="false">
    <div class="upload-head">
      <div>
        <p class="upload-eyebrow">Project Files</p>
        <div class="upload-title-row">
          <h2>项目文件上传</h2>
          <n-tag :type="uploadStatusType" round size="small">{{ uploadStatusLabel }}</n-tag>
        </div>
        <p>选择项目文件夹后，前端会先筛选文件，再按每批最多 50 个自动上传并处理失败重试。</p>
      </div>
      <div class="upload-actions">
        <n-button :disabled="uploading" @click="openDirectoryPicker">重新选择</n-button>
        <n-button type="primary" :loading="uploading" @click="openDirectoryPicker">
          {{ uploading ? '正在上传' : '选择文件夹' }}
        </n-button>
      </div>
      <input
        ref="directoryInput"
        class="directory-input"
        type="file"
        multiple
        directory=""
        webkitdirectory=""
        @change="handleDirectoryChange"
      />
    </div>

    <n-alert class="filter-alert" type="info" :show-icon="false">
      会排除依赖、构建产物、缓存、环境变量、可执行文件、压缩包和媒体文件；单文件最大 50MB，单批原始文件总大小不超过 240MB。
    </n-alert>

    <div v-if="viewState === 'idle'" class="upload-placeholder">
      <n-empty description="尚未选择项目文件夹">
        <template #extra>
          <n-button type="primary" @click="openDirectoryPicker">选择文件夹并上传</n-button>
        </template>
      </n-empty>
    </div>

    <div v-else-if="viewState === 'empty'" class="empty-project-mock">
      <span class="mock-badge">本地 Mock 状态</span>
      <h3>项目内容为空</h3>
      <p>当前文件夹中没有可上传文件，前端未调用任何后端接口。</p>
      <div v-if="rejectedFiles.length" class="filter-summary">
        <span>已筛除 {{ rejectedFiles.length }} 个文件：</span>
        <n-tag
          v-for="item in rejectedReasonSummary"
          :key="item.reason"
          size="small"
          round
        >
          {{ item.reason }} {{ item.count }}
        </n-tag>
      </div>
    </div>

    <template v-else>
      <div class="upload-metrics">
        <div>
          <span>符合条件</span>
          <strong>{{ originalTotalFiles }}</strong>
        </div>
        <div>
          <span>已筛除</span>
          <strong>{{ rejectedFiles.length }}</strong>
        </div>
        <div>
          <span>当前轮次</span>
          <strong>{{ currentAttempt }}/3</strong>
        </div>
        <div>
          <span>当前批次</span>
          <strong>{{ completedBatchCount }}/{{ currentBatchCount }}</strong>
        </div>
      </div>

      <div class="progress-panel">
        <div class="progress-copy">
          <div>
            <strong>{{ selectedDirectoryName }}</strong>
            <span>{{ uploadProgressText }}</span>
          </div>
          <span>{{ uploadPercentage }}%</span>
        </div>
        <n-progress
          type="line"
          :percentage="uploadPercentage"
          :show-indicator="false"
          :status="viewState === 'needs-update' ? 'warning' : 'default'"
          color="#2f7df6"
        />
      </div>

      <div v-if="rejectedFiles.length" class="filter-summary">
        <span>筛选结果：</span>
        <n-tag
          v-for="item in rejectedReasonSummary"
          :key="item.reason"
          size="small"
          round
        >
          {{ item.reason }} {{ item.count }}
        </n-tag>
      </div>

      <n-alert v-if="viewState === 'success'" type="success" title="项目文件上传完成">
        {{ originalTotalFiles }} 个文件已全部上传，后端已根据 MySQL 数据重建 index.json。
      </n-alert>

      <n-alert
        v-if="viewState === 'needs-update'"
        type="warning"
        title="三轮上传结束，仍有文件失败"
      >
        共 {{ finalFailures.length }} 个文件未上传成功。后续请点击“更新项目”重新处理这些文件。
      </n-alert>

      <n-alert v-if="viewState === 'error'" type="error" title="上传流程中断">
        {{ fatalErrorMessage }}
      </n-alert>

      <div v-if="finalFailures.length" class="failure-list">
        <div class="failure-list-head">
          <strong>未上传文件</strong>
          <span>{{ finalFailures.length }} 个</span>
        </div>
        <div
          v-for="failure in finalFailures.slice(0, 20)"
          :key="failure.candidate.clientFileId"
          class="failure-item"
        >
          <span>{{ failure.candidate.relativePath }}</span>
          <small>{{ failure.errorMessage }}</small>
        </div>
        <p v-if="finalFailures.length > 20" class="failure-more">
          另有 {{ finalFailures.length - 20 }} 个失败文件未展开。
        </p>
      </div>
    </template>
  </n-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { v4 as uuidv4 } from 'uuid'
import { uploadProjectFileBatch } from '@/modules/project/api'
import {
  createProjectFileUploadRound,
  prepareProjectFiles,
  PROJECT_FILE_MAX_ATTEMPTS,
  type PreparedProjectFile,
  type RejectedProjectFile,
} from '@/modules/project/file-upload'
import type {
  ProjectFileUploadBatchResponse,
  UploadProjectFileBatchPayload,
} from '@/modules/project/types'
import { useAuthStore } from '@/stores/auth'

type UploadViewState = 'idle' | 'empty' | 'uploading' | 'success' | 'needs-update' | 'error'

interface UploadFailure {
  candidate: PreparedProjectFile
  errorCode: string
  errorMessage: string
}

interface RoundBatchOutcome {
  candidates: PreparedProjectFile[]
  response: ProjectFileUploadBatchResponse
}

const batchHttpRetryDelaysMs = [300, 600]

const props = defineProps<{
  projectId: number
}>()

const authStore = useAuthStore()
const message = useMessage()
const directoryInput = ref<HTMLInputElement | null>(null)
const viewState = ref<UploadViewState>('idle')
const uploading = ref(false)
const selectedDirectoryName = ref('')
const originalTotalFiles = ref(0)
const remainingFileCount = ref(0)
const currentAttempt = ref(0)
const currentBatchCount = ref(0)
const completedBatchCount = ref(0)
const rejectedFiles = ref<RejectedProjectFile[]>([])
const finalFailures = ref<UploadFailure[]>([])
const fatalErrorMessage = ref('')

const rejectedReasonSummary = computed(() => {
  const counts = new Map<string, number>()
  rejectedFiles.value.forEach((item) => counts.set(item.reason, (counts.get(item.reason) ?? 0) + 1))
  return Array.from(counts, ([reason, count]) => ({ reason, count }))
})

const uploadPercentage = computed(() => {
  if (!originalTotalFiles.value) return 0
  return Math.round(
    ((originalTotalFiles.value - remainingFileCount.value) / originalTotalFiles.value) * 100,
  )
})

const uploadProgressText = computed(() => {
  if (viewState.value === 'uploading') {
    return `第 ${currentAttempt.value} 轮处理中，剩余 ${remainingFileCount.value} 个文件待确认`
  }
  if (viewState.value === 'success') return `${originalTotalFiles.value} 个文件已上传成功`
  if (viewState.value === 'needs-update') return `${remainingFileCount.value} 个文件仍未上传`
  return '上传流程已中断'
})

const uploadStatusLabel = computed(() => {
  const labels: Record<UploadViewState, string> = {
    idle: '待选择',
    empty: '内容为空',
    uploading: '上传中',
    success: '已完成',
    'needs-update': '待更新',
    error: '已中断',
  }
  return labels[viewState.value]
})

const uploadStatusType = computed<'default' | 'info' | 'success' | 'warning' | 'error'>(() => {
  if (viewState.value === 'uploading') return 'info'
  if (viewState.value === 'success') return 'success'
  if (viewState.value === 'needs-update' || viewState.value === 'empty') return 'warning'
  if (viewState.value === 'error') return 'error'
  return 'default'
})

function openDirectoryPicker() {
  if (uploading.value || !directoryInput.value) return
  directoryInput.value.value = ''
  directoryInput.value.click()
}

async function handleDirectoryChange(event: Event) {
  const input = event.target as HTMLInputElement
  const selectedFiles = Array.from(input.files ?? [])
  input.value = ''
  resetUploadView()

  if (!selectedFiles.length) {
    viewState.value = 'empty'
    selectedDirectoryName.value = '空文件夹'
    return
  }

  selectedDirectoryName.value = getDirectoryName(selectedFiles[0])
  const filterResult = prepareProjectFiles(selectedFiles)
  rejectedFiles.value = filterResult.rejectedFiles
  originalTotalFiles.value = filterResult.acceptedFiles.length
  remainingFileCount.value = filterResult.acceptedFiles.length

  if (!filterResult.acceptedFiles.length) {
    viewState.value = 'empty'
    message.info('文件夹中没有符合上传条件的文件，未调用后端接口')
    return
  }

  await startUpload(filterResult.acceptedFiles)
}

async function startUpload(allCandidates: PreparedProjectFile[]) {
  const userId = authStore.user?.id
  if (!userId) {
    viewState.value = 'error'
    fatalErrorMessage.value = '当前登录用户信息不可用，请重新登录后再试。'
    return
  }

  uploading.value = true
  viewState.value = 'uploading'
  const requestId = uuidv4()
  const candidateById = new Map(allCandidates.map((candidate) => [candidate.clientFileId, candidate]))
  let pendingCandidates = allCandidates

  try {
    for (let attemptNo = 1; attemptNo <= PROJECT_FILE_MAX_ATTEMPTS; attemptNo += 1) {
      currentAttempt.value = attemptNo
      const round = createProjectFileUploadRound({
        userId,
        projectId: props.projectId,
        requestId,
        attemptNo,
        originalTotalFiles: allCandidates.length,
        files: pendingCandidates,
      })
      currentBatchCount.value = round.batches.length
      completedBatchCount.value = 0

      const outcomes: RoundBatchOutcome[] = []
      for (const { batch, files, candidates } of round.batches) {
        const response = await uploadBatchWithHttpRetry(props.projectId, {
          manifest: round.manifest,
          batch,
          files,
        })
        outcomes.push({ candidates, response })
        completedBatchCount.value += 1
      }

      const failures = collectRoundFailures(outcomes, candidateById)
      pendingCandidates = failures.map((failure) => failure.candidate)
      remainingFileCount.value = pendingCandidates.length
      finalFailures.value = failures

      if (!pendingCandidates.length) {
        viewState.value = 'success'
        message.success('项目文件上传完成')
        return
      }

      if (attemptNo < PROJECT_FILE_MAX_ATTEMPTS) {
        message.warning(`第 ${attemptNo} 轮有 ${pendingCandidates.length} 个文件失败，正在重新分批上传`)
      }
    }

    viewState.value = 'needs-update'
    message.warning('三轮上传结束，仍有失败文件，请后续点击更新项目重试')
  } catch (error) {
    viewState.value = 'error'
    fatalErrorMessage.value = error instanceof Error ? error.message : '上传流程发生未知错误，请稍后重试。'
    message.error(fatalErrorMessage.value)
  } finally {
    uploading.value = false
  }
}

function collectRoundFailures(
  outcomes: RoundBatchOutcome[],
  candidateById: Map<string, PreparedProjectFile>,
) {
  const failures = new Map<string, UploadFailure>()

  for (const outcome of outcomes) {
    const batchFileIds = new Set(outcome.candidates.map((candidate) => candidate.clientFileId))
    outcome.response.failedFiles.forEach((failedFile) => {
      const candidate = candidateById.get(failedFile.clientFileId)
      if (!candidate || !batchFileIds.has(failedFile.clientFileId)) {
        throw new Error(`上传响应包含未知文件ID：${failedFile.clientFileId}`)
      }
      failures.set(candidate.clientFileId, {
        candidate,
        errorCode: failedFile.errorCode || 'FILE_UPLOAD_FAILED',
        errorMessage: failedFile.errorMessage || '文件上传失败',
      })
    })
  }

  return Array.from(failures.values())
}

async function uploadBatchWithHttpRetry(
  projectId: number,
  payload: UploadProjectFileBatchPayload,
) {
  let lastError: unknown

  for (let sendIndex = 0; sendIndex <= batchHttpRetryDelaysMs.length; sendIndex += 1) {
    try {
      return await uploadProjectFileBatch(projectId, payload)
    } catch (error) {
      lastError = error
      const retryDelay = batchHttpRetryDelaysMs[sendIndex]
      if (retryDelay === undefined) break
      await wait(retryDelay)
    }
  }

  const errorMessage = lastError instanceof Error ? lastError.message : '批次请求失败'
  throw new Error(`批次请求补发两次后仍失败，上传流程已中断：${errorMessage}`)
}

function wait(milliseconds: number) {
  return new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds))
}

function resetUploadView() {
  viewState.value = 'idle'
  selectedDirectoryName.value = ''
  originalTotalFiles.value = 0
  remainingFileCount.value = 0
  currentAttempt.value = 0
  currentBatchCount.value = 0
  completedBatchCount.value = 0
  rejectedFiles.value = []
  finalFailures.value = []
  fatalErrorMessage.value = ''
}

function getDirectoryName(file: File) {
  const [directoryName] = file.webkitRelativePath.split('/')
  return directoryName || '项目文件夹'
}
</script>

<style scoped>
.upload-card {
  overflow: hidden;
}

.upload-head,
.upload-title-row,
.upload-actions,
.filter-summary,
.progress-copy,
.failure-list-head {
  display: flex;
  align-items: center;
}

.upload-head {
  justify-content: space-between;
  gap: 24px;
}

.upload-head h2,
.empty-project-mock h3 {
  margin: 0;
  color: var(--pm-text);
}

.upload-head > div:first-child > p:last-child,
.empty-project-mock p {
  margin: 8px 0 0;
  color: var(--pm-text-secondary);
  line-height: 1.7;
}

.upload-eyebrow {
  margin: 0 0 6px;
  color: var(--pm-blue-dark);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.upload-title-row,
.upload-actions,
.filter-summary {
  gap: 10px;
}

.directory-input {
  display: none;
}

.filter-alert {
  margin-top: 18px;
}

.upload-placeholder,
.empty-project-mock {
  margin-top: 20px;
  border: 1px dashed #cbd8eb;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(234, 242, 255, 0.7), rgba(234, 248, 242, 0.7));
}

.upload-placeholder {
  padding: 42px 24px;
}

.empty-project-mock {
  position: relative;
  padding: 34px;
  border-left: 4px solid var(--pm-yellow);
}

.mock-badge {
  display: inline-flex;
  margin-bottom: 14px;
  padding: 5px 10px;
  border-radius: 999px;
  color: #9a650d;
  background: var(--pm-yellow-soft);
  font-size: 12px;
  font-weight: 700;
}

.upload-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 20px;
}

.upload-metrics > div {
  padding: 16px;
  border: 1px solid var(--pm-border-light);
  border-radius: 14px;
  background: rgba(248, 250, 245, 0.8);
}

.upload-metrics span,
.progress-copy span,
.failure-list-head span {
  color: var(--pm-text-secondary);
  font-size: 13px;
}

.upload-metrics strong {
  display: block;
  margin-top: 8px;
  color: var(--pm-text);
  font-size: 26px;
}

.progress-panel {
  margin: 20px 0;
}

.progress-copy {
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 10px;
}

.progress-copy div {
  display: grid;
  gap: 4px;
}

.filter-summary {
  flex-wrap: wrap;
  margin: 16px 0;
  color: var(--pm-text-secondary);
  font-size: 13px;
}

.failure-list {
  margin-top: 16px;
  padding: 16px;
  border: 1px solid #f0d39b;
  border-radius: 14px;
  background: #fffaf0;
}

.failure-list-head {
  justify-content: space-between;
  margin-bottom: 10px;
}

.failure-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 0.5fr);
  gap: 16px;
  padding: 9px 0;
  border-top: 1px solid rgba(216, 145, 30, 0.16);
}

.failure-item span {
  overflow: hidden;
  color: var(--pm-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.failure-item small,
.failure-more {
  color: #9a650d;
}

.failure-more {
  margin: 10px 0 0;
  font-size: 12px;
}
</style>
