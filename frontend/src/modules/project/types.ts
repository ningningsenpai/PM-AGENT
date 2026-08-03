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
  projectId: number
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
