export type FileUploadStatus =
  | 'pending'
  | 'staging'
  | 'staged'
  | 'uploading'
  | 'uploaded'
  | 'retry_pending'
  | 'retrying'
  | 'failed'
  | 'skipped'

export interface SelectedProjectFile {
  file: File
  relativePath: string
  uploadAllowed: boolean
  analysisEligible: boolean
  reason?: string
}

export interface SelectedDirectory {
  name: string
  files: SelectedProjectFile[]
  totalSize: number
}

export interface ProjectForm {
  name: string
  description: string
  startDate: string | null
  endDate: string | null
}

export interface ProjectResponse {
  id: number
  name: string
}

export interface ManifestItem {
  relativePath: string
  sizeBytes: number
  lastModifiedEpochMs: number
  contentType: string
}

export interface ProjectFileResponse {
  id: number
  relativePath: string
  originalFileName: string
  sizeBytes: number
  analysisEligible: boolean
  analysisSkipReason?: string
  uploadStatus: FileUploadStatus
  retryCount: number
  nextRetryAt?: string
  lastErrorMessage?: string
  storageVerifyStatus: string
}

export interface FileUploadBatchResponse {
  id: number
  projectId: number
  rootDirectoryName: string
  status: string
  totalFileCount: number
  acceptedFileCount: number
  skippedFileCount: number
  uploadedFileCount: number
  retryFileCount: number
  failedFileCount: number
  totalSizeBytes: number
  uploadedSizeBytes: number
  files: ProjectFileResponse[]
}

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  traceId: string
}
