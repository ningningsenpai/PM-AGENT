export type ProjectStatus = 'initializing' | 'active' | 'init_failed'

export interface ProjectSummary {
  id: string
  projectName: string
  status: ProjectStatus
  recordStatus: 'enabled' | 'disabled'
  createdAt: string
  updatedAt: string
}
export type ProjectDetail = ProjectSummary
export interface CreateProjectRequest { projectName: string }

export interface UploadProjectFilePayload {
  file: File
  relativePath: string
  sourceMtimeMs: number
  idempotencyKey: string
}

export interface ProjectFileUploadResponse {
  fileId: number
  relativePath: string
  fileName: string
  success: boolean
  status: string
  uploadStatus: string
  errorCode: string | null
  errorMessage: string | null
}

export interface ProjectFileResponse {
  id: number
  projectId: string
  businessCode: string
  relativePath: string
  fileName: string
  storageName: string
  minioPath: string
  extension: string | null
  contentType: string
  sizeBytes: number
  sourceMtimeMs: number
  quickFingerprint: string
  contentHash: string
  status: string
  uploadStatus: string
  analysisStatus: 'pending' | 'success' | 'failed' | 'unavailable'
  detailRef: string | null
  lastErrorCode: string | null
  lastErrorMessage: string | null
  lastFailedAt: string | null
  parseAttempts: number
  lockVersion: number
  createdAt: string
  updatedAt: string
}

export interface OverwriteProjectFilePayload extends UploadProjectFilePayload {
  fileId: number
  lockVersion: number
}

export interface UpdateProjectFilePathPayload {
  fileId: number
  relativePath: string
  sourceMtimeMs: number
  lockVersion: number
}

export interface ProjectFileSyncManifestItem {
  relativePath: string
  sizeBytes: number
  sourceMtimeMs: number
  contentHash: string | null
  contentType: string | null
}

export interface ProjectFileSyncPlanRequest {
  snapshotComplete: boolean
  scope: 'project'
  items: ProjectFileSyncManifestItem[]
}

export interface ProjectFileSyncLocalItem {
  relativePath: string
  sizeBytes: number
  sourceMtimeMs: number
  contentHash: string
  contentType: string
}

export interface ProjectFileSyncRemoteItem {
  remoteFileId: number
  remoteRelativePath: string
  remoteSizeBytes: number
  remoteSourceMtimeMs: number
  remoteContentHash: string
  remoteContentType: string
  lockVersion: number
  remoteStatus: string
  remoteUploadStatus: string
}

export interface ProjectFileSyncMatchedItem
  extends ProjectFileSyncLocalItem,
    ProjectFileSyncRemoteItem {}

export interface ProjectFileSyncRejectedItem {
  relativePath: string
  errorCode: string
  errorMessage: string
  remoteFileId?: number | null
  remoteRelativePath?: string | null
  lockVersion?: number | null
}

export interface ProjectFileSyncAmbiguousItem {
  contentHash: string
  localItems: ProjectFileSyncLocalItem[]
  remoteItems: ProjectFileSyncRemoteItem[]
}

export interface ProjectFileSyncPlan {
  snapshotComplete: boolean
  scope: 'project'
  unchanged: ProjectFileSyncMatchedItem[]
  modified: ProjectFileSyncMatchedItem[]
  moved: ProjectFileSyncMatchedItem[]
  added: ProjectFileSyncLocalItem[]
  deleted: ProjectFileSyncRemoteItem[]
  rejected: ProjectFileSyncRejectedItem[]
  ambiguous: ProjectFileSyncAmbiguousItem[]
}

export interface ProjectFileParseFailure {
  fileId: number
  relativePath: string
  errorCode: string
  errorMessage: string
}

export interface ProjectFileParseResult {
  runId?: string | null
  status: 'success' | 'partial'
  candidateCount: number
  successCount: number
  failureCount: number
  failures: ProjectFileParseFailure[]
  specificationStatus: 'updated' | 'kept' | 'failed'
  indexStatus: 'updated' | 'failed'
}

export interface ProjectFileParseRecovery {
  runId: string | null
  status: 'absent' | 'running' | 'success' | 'failed'
  retryable: boolean
  retryMode: 'same_key' | 'new_key' | null
  leaseUntil: string | null
  serverTime: string
  result: ProjectFileParseResult | null
  error: string | null
}
