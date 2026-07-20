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
