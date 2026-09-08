import type {
  CreateProjectRequest,
  OverwriteProjectFilePayload,
  ProjectDetail,
  ProjectFileParseResult,
  ProjectFileResponse,
  ProjectFileSyncLocalItem,
  ProjectFileSyncMatchedItem,
  ProjectFileSyncPlan,
  ProjectFileSyncPlanRequest,
  ProjectFileSyncRemoteItem,
  ProjectFileUploadResponse,
  ProjectSummary,
  UpdateProjectFilePathPayload,
  UploadProjectFilePayload,
} from '@/modules/project/types'
import { hashProjectFile } from '@/modules/project/project-update'

const projects: ProjectDetail[] = [{ id: '1', projectName: '演示项目', status: 'active', recordStatus: 'enabled', createdAt: '2026-06-01T09:00:00', updatedAt: '2026-06-01T09:00:00' }]
export async function mockListProjects(): Promise<ProjectSummary[]> { return [...projects] }
export async function mockGetProjectDetail(id: string): Promise<ProjectDetail> {
  const project = projects.find((item) => item.id === id)
  if (!project) throw new Error('项目不存在')
  return project
}
export async function mockCreateProject(payload: CreateProjectRequest): Promise<ProjectDetail> {
  const project: ProjectDetail = { id: String(projects.length + 1), projectName: payload.projectName, status: 'active', recordStatus: 'enabled', createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }
  projects.unshift(project)
  return project
}

let mockFileId = 1
const projectFiles = new Map<string, ProjectFileResponse[]>()

export async function mockUploadProjectFile(
  projectId: string,
  payload: UploadProjectFilePayload,
): Promise<ProjectFileUploadResponse> {
  const now = new Date().toISOString()
  const fileId = mockFileId++
  const contentHash = await hashProjectFile(payload.file)
  const record: ProjectFileResponse = {
    id: fileId,
    projectId,
    businessCode: 'project',
    relativePath: payload.relativePath,
    fileName: payload.file.name,
    storageName: payload.file.name,
    minioPath: `project/${payload.file.name}`,
    extension: payload.file.name.split('.').pop() ?? null,
    contentType: payload.file.type || 'application/octet-stream',
    sizeBytes: payload.file.size,
    sourceMtimeMs: payload.sourceMtimeMs,
    quickFingerprint: contentHash,
    contentHash,
    status: 'active',
    uploadStatus: 'success',
    analysisStatus: 'pending',
    detailRef: null, lastErrorCode: null, lastErrorMessage: null, lastFailedAt: null,
    parseAttempts: 0,
    lockVersion: 0,
    createdAt: now,
    updatedAt: now,
  }
  const files = projectFiles.get(projectId) ?? []
  files.push(record)
  projectFiles.set(projectId, files)
  return {
    fileId,
    relativePath: payload.relativePath,
    fileName: payload.file.name,
    success: true,
    status: 'active',
    uploadStatus: 'success',
    errorCode: null,
    errorMessage: null,
  }
}

export async function mockListProjectFiles(projectId: string): Promise<ProjectFileResponse[]> {
  return [...(projectFiles.get(projectId) ?? [])]
}

export async function mockOverwriteProjectFile(
  projectId: string,
  payload: OverwriteProjectFilePayload,
): Promise<ProjectFileResponse> {
  const file = requireMockFile(projectId, payload.fileId)
  file.contentHash = await hashProjectFile(payload.file)
  file.sizeBytes = payload.file.size
  file.contentType = payload.file.type || 'application/octet-stream'
  file.sourceMtimeMs = payload.sourceMtimeMs
  file.status = 'active'
  file.uploadStatus = 'success'
  file.parseAttempts = 0
  file.lockVersion += 1
  file.updatedAt = new Date().toISOString()
  return file
}

export async function mockUpdateProjectFilePath(
  projectId: string,
  payload: UpdateProjectFilePathPayload,
): Promise<ProjectFileResponse> {
  const file = requireMockFile(projectId, payload.fileId)
  file.relativePath = payload.relativePath
  file.fileName = payload.relativePath.split('/').pop() || file.fileName
  file.sourceMtimeMs = payload.sourceMtimeMs
  file.lockVersion += 1
  file.updatedAt = new Date().toISOString()
  return file
}

export async function mockDeleteProjectFile(
  projectId: string,
  fileId: number,
  _lockVersion: number,
): Promise<void> {
  const files = projectFiles.get(projectId) ?? []
  projectFiles.set(
    projectId,
    files.filter((file) => file.id !== fileId),
  )
}

export async function mockPlanProjectFileSync(
  projectId: string,
  request: ProjectFileSyncPlanRequest,
): Promise<ProjectFileSyncPlan> {
  const remoteFiles = projectFiles.get(projectId) ?? []
  const remoteByPath = new Map(remoteFiles.map((file) => [file.relativePath, file]))
  const matchedRemoteIds = new Set<number>()
  const unchanged: ProjectFileSyncMatchedItem[] = []
  const modified: ProjectFileSyncMatchedItem[] = []
  const moved: ProjectFileSyncMatchedItem[] = []
  const added: ProjectFileSyncLocalItem[] = []
  const rejected: ProjectFileSyncPlan['rejected'] = []
  const ambiguous: ProjectFileSyncPlan['ambiguous'] = []
  const unmatchedLocal: ProjectFileSyncLocalItem[] = []

  for (const item of request.items) {
    const remote = remoteByPath.get(item.relativePath)
    if (!item.contentHash) {
      if (remote) matchedRemoteIds.add(remote.id)
      rejected.push({
        relativePath: item.relativePath,
        errorCode: 'FRONTEND_FILE_REJECTED',
        errorMessage: '文件未通过前端筛选',
        remoteFileId: remote?.id,
        remoteRelativePath: remote?.relativePath,
        lockVersion: remote?.lockVersion,
      })
      continue
    }

    const local = toMockLocalItem(item)
    if (!remote) {
      unmatchedLocal.push(local)
      continue
    }
    matchedRemoteIds.add(remote.id)
    const matched = { ...local, ...toMockRemoteItem(remote) }
    if (
      remote.status === 'active' &&
      remote.uploadStatus === 'success' &&
      remote.contentHash === local.contentHash
    ) {
      unchanged.push(matched)
    } else {
      modified.push(matched)
    }
  }

  const unmatchedRemote = remoteFiles.filter(
    (file) =>
      !matchedRemoteIds.has(file.id) &&
      file.status === 'active' &&
      file.uploadStatus === 'success',
  )
  const localByHash = groupBy(unmatchedLocal, (item) => item.contentHash)
  const remoteByHash = groupBy(unmatchedRemote, (item) => item.contentHash)

  for (const [contentHash, localItems] of localByHash) {
    const remoteItems = remoteByHash.get(contentHash) ?? []
    if (localItems.length === 1 && remoteItems.length === 1) {
      const [local] = localItems
      const [remote] = remoteItems
      moved.push({ ...local, ...toMockRemoteItem(remote) })
      matchedRemoteIds.add(remote.id)
      continue
    }
    if (remoteItems.length) {
      ambiguous.push({
        contentHash,
        localItems,
        remoteItems: remoteItems.map(toMockRemoteItem),
      })
      remoteItems.forEach((remote) => matchedRemoteIds.add(remote.id))
      continue
    }
    added.push(...localItems)
  }

  return {
    snapshotComplete: request.snapshotComplete,
    scope: request.scope,
    unchanged,
    modified,
    moved,
    added,
    deleted: request.snapshotComplete
      ? remoteFiles
          .filter((file) => !matchedRemoteIds.has(file.id))
          .map(toMockRemoteItem)
      : [],
    rejected,
    ambiguous,
  }
}

export async function mockRequestProjectFileParsing(
  projectId: string,
): Promise<ProjectFileParseResult> {
  const candidateCount = (projectFiles.get(projectId) ?? []).filter(
    (file) => file.status === 'active' && file.uploadStatus === 'success',
  ).length
  return {
    status: 'success',
    candidateCount,
    successCount: candidateCount,
    failureCount: 0,
    failures: [],
    specificationStatus: 'updated',
    indexStatus: 'updated',
  }
}

function toMockLocalItem(
  item: ProjectFileSyncPlanRequest['items'][number],
): ProjectFileSyncLocalItem {
  return {
    relativePath: item.relativePath,
    sizeBytes: item.sizeBytes,
    sourceMtimeMs: item.sourceMtimeMs,
    contentHash: item.contentHash ?? '',
    contentType: item.contentType || 'application/octet-stream',
  }
}

function toMockRemoteItem(file: ProjectFileResponse): ProjectFileSyncRemoteItem {
  return {
    remoteFileId: file.id,
    remoteRelativePath: file.relativePath,
    remoteSizeBytes: file.sizeBytes,
    remoteSourceMtimeMs: file.sourceMtimeMs,
    remoteContentHash: file.contentHash,
    remoteContentType: file.contentType,
    lockVersion: file.lockVersion,
    remoteStatus: file.status,
    remoteUploadStatus: file.uploadStatus,
  }
}

function groupBy<T>(items: T[], keyOf: (item: T) => string) {
  const groups = new Map<string, T[]>()
  for (const item of items) {
    const key = keyOf(item)
    groups.set(key, [...(groups.get(key) ?? []), item])
  }
  return groups
}

function requireMockFile(projectId: string, fileId: number) {
  const file = (projectFiles.get(projectId) ?? []).find((item) => item.id === fileId)
  if (!file) throw new Error('项目文件不存在')
  return file
}
