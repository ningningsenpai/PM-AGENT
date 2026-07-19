export type ProjectStatus = 'not_started' | 'running' | 'paused' | 'delayed' | 'done' | 'archived'

export interface ProjectSummary {
  id: number
  name: string
  code?: string
  description?: string
  ownerName: string
  status: ProjectStatus
  startDate: string
  endDate: string
  taskTotal: number
  doneTaskTotal: number
}

export interface ProjectDetail extends ProjectSummary {
  memberTotal: number
  riskTotal: number
}

export interface CreateProjectRequest {
  name: string
  code?: string
  description?: string
  startDate?: string
  endDate?: string
}

export type ProjectFileBusinessCode = 'project'
export type ProjectFileUploadExecutionStatus = 'initial' | 'retry'
export type ProjectFileUploadBatchStatus = 'waiting' | 'processing' | 'completed'
export type ProjectFileUploadRequestStatus =
  | 'uploading'
  | 'awaiting_retry'
  | 'completed'
  | 'completed_with_failures'

export interface ProjectFileUploadBatchSummary {
  batchId: string
  fileCount: number
}

export interface ProjectFileUploadManifest {
  userId: number
  projectId: number
  requestId: string
  executionStatus: ProjectFileUploadExecutionStatus
  attemptNo: number
  originalTotalFiles: number
  roundTotalFiles: number
  totalBatchCount: number
  batches: ProjectFileUploadBatchSummary[]
}

export interface ProjectFileUploadFileInfo {
  clientFileId: string
  businessCode: ProjectFileBusinessCode
  relativePath: string
  fileName: string
  sizeBytes: number
  sourceMtimeMs: number
}

export interface ProjectFileUploadBatch {
  userId: number
  projectId: number
  requestId: string
  attemptNo: number
  batchId: string
  idempotencyKey: string
  fileCount: number
  files: ProjectFileUploadFileInfo[]
}

export interface ProjectFileUploadFailedFile {
  clientFileId: string
  relativePath: string
  fileName: string
  sizeBytes: number
  sourceMtimeMs: number
  errorCode: string | null
  errorMessage: string | null
}

export interface ProjectFileUploadBatchResponse {
  uploadRequestId: number
  requestId: string
  batchId: string
  attemptNo: number
  batchStatus: ProjectFileUploadBatchStatus
  requestStatus: ProjectFileUploadRequestStatus
  totalFiles: number
  completedFiles: number
  succeededFiles: number
  batchSucceededFiles: number
  batchFailedFiles: number
  failedFiles: ProjectFileUploadFailedFile[]
  requiresRetry: boolean
  requiresProjectUpdate: boolean
}

export interface UploadProjectFileBatchPayload {
  manifest: ProjectFileUploadManifest
  batch: ProjectFileUploadBatch
  files: File[]
}
