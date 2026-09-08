<template>
  <n-card class="glass-card upload-card" :bordered="false">
    <div class="upload-head">
      <div>
        <p class="upload-eyebrow">Project Files</p>
        <div class="upload-title-row">
          <h2>项目文件同步</h2>
          <n-tag :type="uploadStatusType" round size="small">{{ uploadStatusLabel }}</n-tag>
        </div>
        <p>选择项目文件夹后，后端会统一规划新增、修改、移动和删除，再按计划同步。</p>
      </div>
      <div class="upload-actions">
        <n-button type="error" secondary :disabled="uploading" @click="clearProjectFiles">
          清空项目文件
        </n-button>
        <n-button :disabled="uploading" @click="openDirectoryPicker">重新选择</n-button>
        <n-button type="primary" :loading="uploading" @click="openDirectoryPicker">
          {{ uploading ? '正在同步' : '选择文件夹' }}
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
      单文件最大 50MB；文件内容使用 SHA-256 比对，删除远端文件前会再次确认。
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
          <span>同步总项</span>
          <strong>{{ totalFileCount }}</strong>
        </div>
        <div>
          <span>已处理</span>
          <strong>{{ processedFileCount }}</strong>
        </div>
        <div>
          <span>同步成功</span>
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

      <n-alert v-if="viewState === 'success'" type="success" title="项目文件同步完成">
        {{ completionSummary }}
      </n-alert>

      <n-alert
        v-if="viewState === 'needs-update'"
        type="warning"
        title="存在未同步成功的文件"
      >
        {{ completionSummary }} 共 {{ finalFailures.length }} 个文件失败或未通过校验，可重新选择目录继续同步。
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
import { useDialog, useMessage } from 'naive-ui'
import {
  deleteProjectFile,
  overwriteProjectFile,
  planProjectFileSync,
  requestProjectFileParsing,
  updateProjectFilePath,
  uploadProjectFile,
} from '@/modules/project/api'
import type { PreparedProjectFile, RejectedProjectFile } from '@/modules/project/file-upload'
import { prepareProjectFileSync } from '@/modules/project/project-sync'
import type {
  ProjectFileParseResult,
  ProjectFileSyncPlan,
  ProjectFileSyncRemoteItem,
} from '@/modules/project/types'

type UploadViewState = 'idle' | 'empty' | 'uploading' | 'success' | 'needs-update'

interface UploadFailure {
  relativePath: string
  errorMessage: string
}

const props = defineProps<{
  projectId: string
}>()

const dialog = useDialog()
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
const parseResult = ref<ProjectFileParseResult | null>(null)

const rejectedReasonSummary = computed(() => {
  const counts = new Map<string, number>()
  rejectedFiles.value.forEach((item) => counts.set(item.reason, (counts.get(item.reason) ?? 0) + 1))
  return Array.from(counts, ([reason, count]) => ({ reason, count }))
})

const uploadPercentage = computed(() => {
  if (!totalFileCount.value) return 0
  return Math.min(100, Math.round((processedFileCount.value / totalFileCount.value) * 100))
})

const uploadProgressText = computed(() => {
  if (viewState.value === 'uploading') {
    const currentFile = Math.min(processedFileCount.value + 1, totalFileCount.value)
    return `正在处理第 ${currentFile} 个文件，共 ${totalFileCount.value} 个`
  }
  if (viewState.value === 'success') return `${succeededFileCount.value} 个文件已同步`
  return `${finalFailures.value.length} 个文件需要后续更新`
})

const completionSummary = computed(() => {
  if (!parseResult.value) return `${succeededFileCount.value} 个项目文件状态已同步。`
  const specificationText = {
    updated: '项目规范已刷新',
    kept: '项目规范保持不变',
    failed: '项目规范刷新失败',
  }[parseResult.value.specificationStatus]
  const indexText = parseResult.value.indexStatus === 'updated' ? '索引已发布' : '索引发布失败'
  return `文件解析 ${parseResult.value.successCount}/${parseResult.value.candidateCount} 成功，${specificationText}，${indexText}。`
})

const uploadStatusLabel = computed(() => {
  const labels: Record<UploadViewState, string> = {
    idle: '待选择',
    empty: '内容为空',
    uploading: '同步中',
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

  try {
    const selection = await prepareProjectFileSync(selectedFiles)
    rejectedFiles.value = selection.localRejections
    const plan = await planProjectFileSync(props.projectId, selection.request)
    const localIssueCount = recordPlanIssues(plan, selection.localRejections)
    const deletionItems = getDeletionItems(plan)
    totalFileCount.value = countPlanItems(plan) + localIssueCount
    processedFileCount.value =
      plan.unchanged.length +
      plan.rejected.length +
      countUnresolvedAmbiguousItems(plan) +
      localIssueCount
    succeededFileCount.value = plan.unchanged.length

    const deletionApproved = deletionItems.length
      ? await confirmRemoteDeletion(plan, deletionItems)
      : true
    const nonDeletionSucceeded = await executeNonDeletionPlan(plan, selection.filesByPath)
    const canDelete =
      deletionApproved &&
      nonDeletionSucceeded &&
      plan.rejected.length === 0 &&
      localIssueCount === 0

    if (canDelete) {
      await executeDeletionPlan(deletionItems)
    } else if (deletionItems.length) {
      const reason = deletionApproved
        ? '存在非删除动作失败或拒绝项，已跳过删除'
        : '用户取消删除，远端文件已保留'
      recordSkippedDeletions(deletionItems, reason)
    }

    const result = await requestProjectFileParsing(props.projectId)
    applyParseResult(result)
  } catch (error) {
    recordFailure(
      '项目文件同步',
      error instanceof Error ? error.message : '项目文件同步或上下文刷新失败',
    )
  } finally {
    uploading.value = false
  }

  finishUploadView()
}

async function clearProjectFiles() {
  if (uploading.value) return
  resetUploadView()
  selectedDirectoryName.value = '项目全部文件'
  uploading.value = true
  viewState.value = 'uploading'

  try {
    const plan = await planProjectFileSync(props.projectId, {
      snapshotComplete: true,
      scope: 'project',
      items: [],
    })
    totalFileCount.value = plan.deleted.length
    if (plan.deleted.length && !(await confirmClearProjectFiles(plan))) {
      resetUploadView()
      message.info('已取消清空项目文件')
      return
    }

    await executeDeletionPlan(plan.deleted)
    const result = await requestProjectFileParsing(props.projectId)
    applyParseResult(result)
  } catch (error) {
    recordFailure(
      '项目文件清空',
      error instanceof Error ? error.message : '项目文件清空或上下文刷新失败',
    )
  } finally {
    uploading.value = false
  }

  finishUploadView()
}

function finishUploadView() {
  if (finalFailures.value.length || parseResult.value?.status === 'partial') {
    viewState.value = 'needs-update'
    message.warning('存在未同步或未解析成功的文件，可重新选择目录重试')
  } else {
    viewState.value = 'success'
    message.success('项目文件与项目上下文同步完成')
  }
}

function recordPlanIssues(plan: ProjectFileSyncPlan, localRejections: RejectedProjectFile[]) {
  const serverRejectedPaths = new Set(plan.rejected.map((item) => item.relativePath))
  const localReasonByPath = new Map(localRejections.map((item) => [item.relativePath, item.reason]))

  for (const item of plan.rejected) {
    const errorMessage = localReasonByPath.get(item.relativePath) ?? item.errorMessage
    recordFailure(item.relativePath, errorMessage)
    if (!rejectedFiles.value.some((file) => file.relativePath === item.relativePath)) {
      rejectedFiles.value.push({ relativePath: item.relativePath, reason: errorMessage })
    }
  }
  if (!plan.snapshotComplete) {
    for (const item of plan.ambiguous) {
      const remotePaths = item.remoteItems.map((remote) => remote.remoteRelativePath).join('、')
      for (const local of item.localItems) {
        recordFailure(
          local.relativePath,
          `存在多个相同内容文件，无法确认是否由 ${remotePaths} 移动而来；当前不是完整快照，未执行新增或删除`,
        )
      }
    }
  }

  const localOnlyRejections = localRejections.filter(
    (item) => !serverRejectedPaths.has(item.relativePath),
  )
  localOnlyRejections.forEach((item) => recordFailure(item.relativePath, item.reason))
  return localOnlyRejections.length
}

async function executeNonDeletionPlan(
  plan: ProjectFileSyncPlan,
  filesByPath: Map<string, PreparedProjectFile>,
) {
  let allSucceeded = true

  for (const item of plan.moved) {
    allSucceeded =
      (await runSyncOperation(item.relativePath, () =>
        updateProjectFilePath(props.projectId, {
          fileId: item.remoteFileId,
          relativePath: item.relativePath,
          sourceMtimeMs: item.sourceMtimeMs,
          lockVersion: item.lockVersion,
        }),
      )) && allSucceeded
  }
  for (const item of plan.modified) {
    const local = filesByPath.get(item.relativePath)
    allSucceeded =
      (await runLocalFileOperation(item.relativePath, local, (file) =>
        overwriteProjectFile(props.projectId, {
          ...file,
          fileId: item.remoteFileId,
          lockVersion: item.lockVersion,
        }),
      )) && allSucceeded
  }
  const addedItems = [
    ...plan.added,
    ...(plan.snapshotComplete ? plan.ambiguous.flatMap((item) => item.localItems) : []),
  ]
  for (const item of addedItems) {
    const local = filesByPath.get(item.relativePath)
    allSucceeded =
      (await runLocalFileOperation(item.relativePath, local, async (file) => {
        const result = await uploadProjectFile(props.projectId, file)
        if (!result.success) throw new Error(result.errorMessage || '文件上传失败')
      })) && allSucceeded
  }

  return allSucceeded
}

async function executeDeletionPlan(files: ProjectFileSyncRemoteItem[]) {
  for (const item of files) {
    await runSyncOperation(item.remoteRelativePath, () =>
      deleteProjectFile(props.projectId, item.remoteFileId, item.lockVersion),
    )
  }
}

async function runLocalFileOperation(
  relativePath: string,
  local: PreparedProjectFile | undefined,
  operation: (file: PreparedProjectFile) => Promise<unknown>,
) {
  if (!local) {
    recordFailure(relativePath, '同步计划中的本地文件已不可用，请重新选择目录')
    processedFileCount.value += 1
    return false
  }
  return runSyncOperation(relativePath, () => operation(local))
}

async function runSyncOperation(relativePath: string, operation: () => Promise<unknown>) {
  try {
    await operation()
    succeededFileCount.value += 1
    return true
  } catch (error) {
    recordFailure(relativePath, error instanceof Error ? error.message : '文件同步失败')
    return false
  } finally {
    processedFileCount.value += 1
  }
}

function applyParseResult(result: ProjectFileParseResult) {
  parseResult.value = result
  result.failures.forEach((failure) => recordFailure(failure.relativePath, failure.errorMessage))
  if (result.failureCount > result.failures.length) {
    recordFailure('文件解析', `另有 ${result.failureCount - result.failures.length} 个文件解析失败`)
  }
  if (result.specificationStatus === 'failed') {
    recordFailure('system/project_specification.json', '项目规范刷新失败，已保留原有规范')
  }
  if (result.indexStatus === 'failed') {
    recordFailure('system/index.json', '项目索引发布失败')
  }
  if (result.status === 'partial' && !result.failureCount && !finalFailures.value.length) {
    recordFailure('项目上下文', '项目上下文仅部分刷新成功')
  }
}

function recordSkippedDeletions(files: ProjectFileSyncRemoteItem[], reason: string) {
  files.forEach((file) => recordFailure(file.remoteRelativePath, reason))
  processedFileCount.value += files.length
}

function recordFailure(relativePath: string, errorMessage: string) {
  finalFailures.value.push({ relativePath, errorMessage })
}

function countPlanItems(plan: ProjectFileSyncPlan) {
  const ambiguousItemCount = plan.snapshotComplete
    ? plan.ambiguous.reduce(
        (count, item) => count + item.localItems.length + item.remoteItems.length,
        0,
      )
    : countUnresolvedAmbiguousItems(plan)
  return (
    plan.unchanged.length +
    plan.modified.length +
    plan.moved.length +
    plan.added.length +
    plan.deleted.length +
    plan.rejected.length +
    ambiguousItemCount
  )
}

function countUnresolvedAmbiguousItems(plan: ProjectFileSyncPlan) {
  if (plan.snapshotComplete) return 0
  return plan.ambiguous.reduce((count, item) => count + Math.max(1, item.localItems.length), 0)
}

function getDeletionItems(plan: ProjectFileSyncPlan) {
  return [
    ...plan.deleted,
    ...(plan.snapshotComplete ? plan.ambiguous.flatMap((item) => item.remoteItems) : []),
  ]
}

function confirmRemoteDeletion(
  plan: ProjectFileSyncPlan,
  files: ProjectFileSyncRemoteItem[],
) {
  const preview = files
    .slice(0, 5)
    .map((file) => file.remoteRelativePath)
    .join('、')
  const ambiguousLocalCount = plan.ambiguous.reduce(
    (count, item) => count + item.localItems.length,
    0,
  )
  const ambiguityNotice = ambiguousLocalCount
    ? `其中有 ${ambiguousLocalCount} 个本地文件存在重复内容，无法确定移动关系，将按新增+删除处理，文件ID会变化。`
    : ''
  return new Promise<boolean>((resolve) => {
    dialog.warning({
      title: '确认删除远端文件',
      content: `${ambiguityNotice}计划删除 ${files.length} 个远端文件：${preview}${
        files.length > 5 ? ' 等' : ''
      }。确认后仍会先执行新增、修改和移动，全部成功才会删除。`,
      positiveText: '确认删除并同步',
      negativeText: '保留远端文件',
      closable: false,
      maskClosable: false,
      onPositiveClick: () => resolve(true),
      onNegativeClick: () => resolve(false),
    })
  })
}

function confirmClearProjectFiles(plan: ProjectFileSyncPlan) {
  const preview = plan.deleted
    .slice(0, 5)
    .map((file) => file.remoteRelativePath)
    .join('、')
  return new Promise<boolean>((resolve) => {
    dialog.error({
      title: '确认清空项目文件',
      content: `将从项目中删除 ${plan.deleted.length} 个文件：${preview}${
        plan.deleted.length > 5 ? ' 等' : ''
      }。文件源对象及其解析详情将被删除，此操作不可撤销。`,
      positiveText: '确认清空',
      negativeText: '取消',
      closable: false,
      maskClosable: false,
      onPositiveClick: () => resolve(true),
      onNegativeClick: () => resolve(false),
    })
  })
}

function resetUploadView() {
  viewState.value = 'idle'
  selectedDirectoryName.value = ''
  totalFileCount.value = 0
  processedFileCount.value = 0
  succeededFileCount.value = 0
  rejectedFiles.value = []
  finalFailures.value = []
  parseResult.value = null
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
