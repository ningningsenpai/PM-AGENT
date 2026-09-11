<template>
  <n-card class="glass-card upload-card" :bordered="false">
    <div class="upload-head">
      <div>
        <p class="upload-eyebrow">项目资料</p>
        <div class="upload-title-row">
          <h2>项目文件同步</h2>
          <n-tag :type="uploadStatusType" round size="small">{{ uploadStatusLabel }}</n-tag>
        </div>
        <p>绑定项目文件夹后，可直接扫描本地变化并按同步计划更新项目文件。</p>
      </div>
      <div class="upload-actions">
        <n-button type="error" secondary :disabled="uploading || disabled" @click="clearProjectFiles">
          清空项目文件
        </n-button>
        <n-button :loading="selecting" :disabled="uploading || disabled" @click="reselectDirectory">
          重新选择
        </n-button>
        <n-button
          type="primary"
          :loading="uploading"
          :disabled="disabled || selecting || !selectedDirectoryName"
          @click="updateProject"
        >
          {{ uploading ? uploadActionLabel : '更新项目' }}
        </n-button>
      </div>
      <input
        ref="directoryInput"
        class="directory-input"
        type="file"
        multiple
        directory=""
        webkitdirectory=""
        @change="handleFallbackDirectoryChange"
      />
    </div>

    <n-alert class="filter-alert" type="info" :show-icon="false">
      更新项目会直接读取已绑定文件夹，规划新增、修改、移动和删除；不支持 ZIP 等压缩包，单文件最大 50MB。
    </n-alert>

    <div v-if="selectedDirectoryName" class="directory-binding">
      <div>
        <span>当前绑定</span>
        <strong>{{ selectedDirectoryName }}</strong>
      </div>
      <span>{{ lastSyncAt ? `上次同步：${formatDate(lastSyncAt)}` : '尚未完成同步' }}</span>
    </div>

    <div v-if="viewState === 'idle'" class="upload-placeholder">
      <n-empty description="尚未绑定本地项目文件夹">
        <template #extra>
          <n-button type="primary" @click="reselectDirectory">绑定项目文件夹</n-button>
        </template>
      </n-empty>
    </div>

    <div v-else-if="viewState === 'ready'" class="ready-project">
      <h3>项目文件夹已绑定</h3>
      <p>点击“更新项目”即可重新扫描当前文件夹，无需再次选择路径。</p>
    </div>

    <div v-else-if="viewState === 'empty'" class="empty-project">
      <h3>项目内容为空</h3>
      <p>当前文件夹中没有文件，前端未调用后端接口。</p>
    </div>

    <template v-else>
      <div class="upload-metrics">
        <div>
          <span>目录文件</span>
          <strong>{{ currentFileCount }}</strong>
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
        {{ completionSummary }} 共 {{ finalFailures.length }} 个文件失败或未通过校验，可点击“更新项目”重试。
      </n-alert>

    </template>
  </n-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { useDialog, useMessage } from 'naive-ui'
import {
  deleteProjectFile,
  overwriteProjectFile,
  planProjectFileSync,
  requestProjectFileParsing,
  updateProjectFilePath,
  uploadProjectFile,
} from '@/modules/project/api'
import {
  projectFileCandidatesFromInput,
  type PreparedProjectFile,
  type ProjectFileCandidate,
  type RejectedProjectFile,
} from '@/modules/project/file-upload'
import { prepareProjectFileSync } from '@/modules/project/project-sync'
import {
  getProjectDirectoryBinding,
  isDirectoryPickerCancelled,
  isProjectDirectoryPickerSupported,
  markProjectDirectorySynced,
  pickProjectDirectory,
  readProjectDirectory,
  saveProjectDirectoryBinding,
  takePendingProjectDirectory,
  verifyProjectDirectoryPermission,
  type ProjectDirectoryHandle,
} from '@/modules/project/project-directory'
import type {
  ProjectFileParseResult,
  ProjectFileSyncPlan,
  ProjectFileSyncRemoteItem,
} from '@/modules/project/types'
import { useAuthStore } from '@/stores/auth'
import { errorMessage, formatDate } from '@/shared/utils/format'

type UploadViewState = 'idle' | 'ready' | 'empty' | 'uploading' | 'success' | 'needs-update'

interface UploadFailure {
  relativePath: string
  errorMessage: string
}

const props = defineProps<{
  projectId: string
  disabled?: boolean
}>()
const emit = defineEmits<{ changed: []; busy: [value: boolean] }>()

const dialog = useDialog()
const message = useMessage()
const auth = useAuthStore()
const directoryInput = ref<HTMLInputElement | null>(null)
const viewState = ref<UploadViewState>('idle')
const uploading = ref(false)
const selecting = ref(false)
const scanning = ref(false)
watch(uploading, (value) => emit('busy', value), { flush: 'sync' })
function guardSync() { if (uploading.value) { message.warning('正在同步文件，请等待操作结束'); return false } }
onBeforeRouteLeave(guardSync)
onBeforeRouteUpdate(guardSync)
const selectedDirectoryName = ref('')
const directoryHandle = ref<ProjectDirectoryHandle | null>(null)
const fallbackFiles = ref<ProjectFileCandidate[]>([])
const lastSyncAt = ref<string | null>(null)
const currentFileCount = ref(0)
const totalFileCount = ref(0)
const processedFileCount = ref(0)
const succeededFileCount = ref(0)
const rejectedFiles = ref<RejectedProjectFile[]>([])
const finalFailures = ref<UploadFailure[]>([])
const parseResult = ref<ProjectFileParseResult | null>(null)
const plannedChangeCount = ref(0)

const uploadActionLabel = computed(() => (scanning.value ? '正在扫描' : '正在同步'))

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
  if (viewState.value === 'success') return `当前目录共 ${currentFileCount.value} 个文件`
  return `${finalFailures.value.length} 个文件需要后续更新`
})

const completionSummary = computed(() => {
  if (!parseResult.value) {
    if (!plannedChangeCount.value && !finalFailures.value.length) {
      return '本地目录与项目文件一致，无需更新。'
    }
    return `本轮 ${plannedChangeCount.value} 项变更已同步，当前目录共 ${currentFileCount.value} 个文件。请在下方单独发起文件解析。`
  }
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
    idle: '未绑定',
    ready: '已绑定',
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

async function initializeDirectory() {
  const pending = takePendingProjectDirectory(props.projectId)
  if (pending) {
    selectedDirectoryName.value = pending.directoryName
    directoryHandle.value = pending.handle ?? null
    fallbackFiles.value = pending.files ?? []
    viewState.value = 'ready'
    if (pending.handle && auth.user?.id) {
      try {
        await saveProjectDirectoryBinding(auth.user.id, props.projectId, pending.handle)
      } catch {
        message.warning('本次可以继续同步，但浏览器未能持久保存项目文件夹')
      }
    }
    await updateProject()
    return
  }

  if (!auth.user?.id) return
  try {
    const binding = await getProjectDirectoryBinding(auth.user.id, props.projectId)
    if (!binding) return
    directoryHandle.value = binding.handle
    selectedDirectoryName.value = binding.directoryName
    lastSyncAt.value = binding.lastSyncAt
    viewState.value = 'ready'
  } catch {
    message.warning('未能读取当前浏览器保存的项目文件夹绑定')
  }
}

onMounted(() => void initializeDirectory())

async function reselectDirectory() {
  if (uploading.value || selecting.value || props.disabled) return
  if (!isProjectDirectoryPickerSupported()) {
    if (directoryInput.value) {
      directoryInput.value.value = ''
      directoryInput.value.click()
    }
    return
  }

  selecting.value = true
  try {
    const handle = await pickProjectDirectory(directoryHandle.value ?? undefined)
    directoryHandle.value = handle
    fallbackFiles.value = []
    selectedDirectoryName.value = handle.name
    lastSyncAt.value = null
    resetUploadView('ready')
    if (auth.user?.id) {
      await saveProjectDirectoryBinding(auth.user.id, props.projectId, handle)
    }
    message.success(`已绑定 ${handle.name}，点击“更新项目”开始同步`)
  } catch (selectionError) {
    if (!isDirectoryPickerCancelled(selectionError)) {
      message.error(errorMessage(selectionError))
    }
  } finally {
    selecting.value = false
  }
}

function handleFallbackDirectoryChange(event: Event) {
  const input = event.target as HTMLInputElement
  const selectedFiles = Array.from(input.files ?? [])
  input.value = ''
  if (!selectedFiles.length) return
  fallbackFiles.value = projectFileCandidatesFromInput(selectedFiles)
  directoryHandle.value = null
  selectedDirectoryName.value = getDirectoryName(selectedFiles[0])
  lastSyncAt.value = null
  resetUploadView('ready')
  message.warning('当前浏览器无法持久绑定目录；本页内可直接更新，刷新后需要重新选择')
}

async function updateProject() {
  if (uploading.value || selecting.value || props.disabled) return
  if (!selectedDirectoryName.value) {
    message.warning('请先重新选择并绑定项目文件夹')
    return
  }

  resetUploadView('ready')
  uploading.value = true
  viewState.value = 'uploading'
  scanning.value = true

  try {
    let selectedFiles = fallbackFiles.value
    if (directoryHandle.value) {
      const permitted = await verifyProjectDirectoryPermission(directoryHandle.value, true)
      if (!permitted) throw new Error('项目文件夹读取权限已失效，请重新授权或重新选择')
      selectedFiles = await readProjectDirectory(directoryHandle.value)
    }
    scanning.value = false

    if (!selectedFiles.length) {
      viewState.value = 'empty'
      message.warning('当前文件夹为空；如需删除服务端文件，请使用“清空项目文件”')
      return
    }

    totalFileCount.value = selectedFiles.length
    const selection = await prepareProjectFileSync(selectedFiles)
    currentFileCount.value = selection.filesByPath.size
    rejectedFiles.value = selection.localRejections
    const plan = await planProjectFileSync(props.projectId, selection.request)
    plannedChangeCount.value =
      plan.modified.length +
      plan.moved.length +
      plan.added.length +
      plan.deleted.length +
      plan.ambiguous.reduce(
        (count, item) => count + item.localItems.length + item.remoteItems.length,
        0,
      )
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

  } catch (error) {
    recordFailure(
      '项目文件同步',
      error instanceof Error ? error.message : '项目文件同步或上下文刷新失败',
    )
  } finally {
    scanning.value = false
    uploading.value = false
  }

  const syncSucceeded =
    !finalFailures.value.length && parseResult.value?.status !== 'partial'
  finishUploadView()
  if (syncSucceeded && directoryHandle.value && auth.user?.id) {
    try {
      const binding = await markProjectDirectorySynced(auth.user.id, props.projectId)
      lastSyncAt.value = binding?.lastSyncAt ?? lastSyncAt.value
    } catch {
      message.warning('文件同步成功，但上次同步时间未能保存到当前浏览器')
    }
  }
}

async function clearProjectFiles() {
  if (uploading.value || props.disabled) return
  resetUploadView(selectedDirectoryName.value ? 'ready' : 'idle')
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
      resetUploadView(selectedDirectoryName.value ? 'ready' : 'idle')
      message.info('已取消清空项目文件')
      return
    }

    await executeDeletionPlan(plan.deleted)
    const result = await requestProjectFileParsing(
      props.projectId,
      undefined,
      crypto.randomUUID(),
    )
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
  emit('changed')
  if (finalFailures.value.length || parseResult.value?.status === 'partial') {
    viewState.value = 'needs-update'
    message.warning('存在未同步或未解析成功的文件，可点击“更新项目”重试')
  } else {
    viewState.value = 'success'
    message.success(
      parseResult.value
        ? '项目文件与项目上下文同步完成'
        : plannedChangeCount.value
          ? '文件同步完成，可在下方发起解析'
          : '项目文件已是最新状态',
    )
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

function resetUploadView(state: UploadViewState = selectedDirectoryName.value ? 'ready' : 'idle') {
  viewState.value = state
  currentFileCount.value = 0
  totalFileCount.value = 0
  processedFileCount.value = 0
  succeededFileCount.value = 0
  rejectedFiles.value = []
  finalFailures.value = []
  parseResult.value = null
  plannedChangeCount.value = 0
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
.progress-copy {
  display: flex;
  align-items: center;
}

.upload-head {
  justify-content: space-between;
  gap: 24px;
}

.upload-head h2,
.empty-project h3,
.ready-project h3 {
  margin: 0;
  color: var(--pm-text);
}

.upload-head > div:first-child > p:last-child,
.empty-project p,
.ready-project p {
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

.directory-binding {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-top: 14px;
  padding: 12px 16px;
  border: 1px solid #d7e4f5;
  border-radius: 14px;
  background: #f7faff;
  color: var(--pm-text-secondary);
  font-size: 13px;
}

.directory-binding div {
  display: flex;
  align-items: center;
  gap: 10px;
}

.directory-binding strong {
  color: var(--pm-text);
  overflow-wrap: anywhere;
}

.upload-placeholder,
.empty-project,
.ready-project {
  margin-top: 20px;
  border: 1px dashed #cbd8eb;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(234, 242, 255, 0.7), rgba(234, 248, 242, 0.7));
}

.upload-placeholder {
  padding: 42px 24px;
}

.empty-project,
.ready-project {
  padding: 34px;
}

.empty-project {
  border-left: 4px solid var(--pm-yellow);
}

.ready-project {
  border-left: 4px solid var(--pm-blue);
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
.progress-copy span {
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

</style>
