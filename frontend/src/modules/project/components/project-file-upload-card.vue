<template>
  <n-card class="glass-card upload-card" :bordered="false">
    <div class="upload-head">
      <div>
        <p class="upload-eyebrow">Project Files</p>
        <div class="upload-title-row">
          <h2>项目文件上传</h2>
          <n-tag :type="uploadStatusType" round size="small">{{ uploadStatusLabel }}</n-tag>
        </div>
        <p>选择项目文件夹后，前端会逐个校验并调用单文件上传接口。</p>
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
      文件通过前端校验后逐个上传；单文件最大 50MB，失败文件不会自动重试。
    </n-alert>

    <div v-if="viewState === 'idle'" class="upload-placeholder">
      <n-empty description="尚未选择项目文件夹">
        <template #extra>
          <n-button type="primary" @click="openDirectoryPicker">选择文件夹并上传</n-button>
        </template>
      </n-empty>
    </div>

    <div v-else-if="viewState === 'empty'" class="empty-project">
      <h3>项目内容为空</h3>
      <p>当前文件夹中没有文件，前端未调用后端接口。</p>
    </div>

    <template v-else>
      <div class="upload-metrics">
        <div>
          <span>文件总数</span>
          <strong>{{ totalFileCount }}</strong>
        </div>
        <div>
          <span>已处理</span>
          <strong>{{ processedFileCount }}</strong>
        </div>
        <div>
          <span>上传成功</span>
          <strong>{{ succeededFileCount }}</strong>
        </div>
        <div>
          <span>失败或跳过</span>
          <strong>{{ finalFailures.length }}</strong>
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
        <span>前端校验未通过：</span>
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
        {{ succeededFileCount }} 个文件已上传，文件解析接口已调用。
      </n-alert>

      <n-alert
        v-if="viewState === 'needs-update'"
        type="warning"
        title="存在未上传成功的文件"
      >
        共 {{ finalFailures.length }} 个文件失败或未通过校验，系统不会自动重试，请后续更新项目。
      </n-alert>

      <div v-if="finalFailures.length" class="failure-list">
        <div class="failure-list-head">
          <strong>待更新文件</strong>
          <span>{{ finalFailures.length }} 个</span>
        </div>
        <div
          v-for="(failure, index) in finalFailures.slice(0, 20)"
          :key="`${failure.relativePath}-${index}`"
          class="failure-item"
        >
          <span>{{ failure.relativePath }}</span>
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
import { requestProjectFileParsing, uploadProjectFile } from '@/modules/project/api'
import {
  validateProjectFile,
  type RejectedProjectFile,
} from '@/modules/project/file-upload'

type UploadViewState = 'idle' | 'empty' | 'uploading' | 'success' | 'needs-update'

interface UploadFailure {
  relativePath: string
  errorMessage: string
}

const props = defineProps<{
  projectId: number
}>()

const message = useMessage()
const directoryInput = ref<HTMLInputElement | null>(null)
const viewState = ref<UploadViewState>('idle')
const uploading = ref(false)
const selectedDirectoryName = ref('')
const totalFileCount = ref(0)
const processedFileCount = ref(0)
const succeededFileCount = ref(0)
const rejectedFiles = ref<RejectedProjectFile[]>([])
const finalFailures = ref<UploadFailure[]>([])

const rejectedReasonSummary = computed(() => {
  const counts = new Map<string, number>()
  rejectedFiles.value.forEach((item) => counts.set(item.reason, (counts.get(item.reason) ?? 0) + 1))
  return Array.from(counts, ([reason, count]) => ({ reason, count }))
})

const uploadPercentage = computed(() => {
  if (!totalFileCount.value) return 0
  return Math.round((processedFileCount.value / totalFileCount.value) * 100)
})

const uploadProgressText = computed(() => {
  if (viewState.value === 'uploading') {
    const currentFile = Math.min(processedFileCount.value + 1, totalFileCount.value)
    return `正在处理第 ${currentFile} 个文件，共 ${totalFileCount.value} 个`
  }
  if (viewState.value === 'success') return `${succeededFileCount.value} 个文件已上传成功`
  return `${finalFailures.value.length} 个文件需要后续更新`
})

const uploadStatusLabel = computed(() => {
  const labels: Record<UploadViewState, string> = {
    idle: '待选择',
    empty: '内容为空',
    uploading: '上传中',
    success: '已完成',
    'needs-update': '待更新',
  }
  return labels[viewState.value]
})

const uploadStatusType = computed<'default' | 'info' | 'success' | 'warning'>(() => {
  if (viewState.value === 'uploading') return 'info'
  if (viewState.value === 'success') return 'success'
  if (viewState.value === 'needs-update' || viewState.value === 'empty') return 'warning'
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
  totalFileCount.value = selectedFiles.length
  uploading.value = true
  viewState.value = 'uploading'
  const acceptedPaths = new Set<string>()

  for (const file of selectedFiles) {
    const validation = validateProjectFile(file, acceptedPaths)
    if (!validation.valid) {
      rejectedFiles.value.push(validation.rejection)
      finalFailures.value.push({
        relativePath: validation.rejection.relativePath,
        errorMessage: validation.rejection.reason,
      })
      processedFileCount.value += 1
      continue
    }

    const candidate = validation.candidate
    try {
      const result = await uploadProjectFile(props.projectId, candidate)
      if (result.success) {
        succeededFileCount.value += 1
      } else {
        finalFailures.value.push({
          relativePath: result.relativePath,
          errorMessage: result.errorMessage || '文件上传失败',
        })
      }
    } catch (error) {
      finalFailures.value.push({
        relativePath: candidate.relativePath,
        errorMessage: error instanceof Error ? error.message : '文件上传失败',
      })
    } finally {
      processedFileCount.value += 1
    }
  }

  try {
    await requestProjectFileParsing(props.projectId)
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : '文件解析接口调用失败'
    message.warning(`文件上传结果已保存，但${errorMessage}`)
  } finally {
    uploading.value = false
  }

  if (finalFailures.value.length) {
    viewState.value = 'needs-update'
    message.warning('存在失败文件，请后续更新项目')
  } else {
    viewState.value = 'success'
    message.success('项目文件上传完成')
  }
}

function resetUploadView() {
  viewState.value = 'idle'
  selectedDirectoryName.value = ''
  totalFileCount.value = 0
  processedFileCount.value = 0
  succeededFileCount.value = 0
  rejectedFiles.value = []
  finalFailures.value = []
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
.empty-project h3 {
  margin: 0;
  color: var(--pm-text);
}

.upload-head > div:first-child > p:last-child,
.empty-project p {
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
.empty-project {
  margin-top: 20px;
  border: 1px dashed #cbd8eb;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(234, 242, 255, 0.7), rgba(234, 248, 242, 0.7));
}

.upload-placeholder {
  padding: 42px 24px;
}

.empty-project {
  padding: 34px;
  border-left: 4px solid var(--pm-yellow);
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
