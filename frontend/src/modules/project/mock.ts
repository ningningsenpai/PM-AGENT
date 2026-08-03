import type {
  CreateProjectRequest,
  OverwriteProjectFilePayload,
  ProjectDetail,
  ProjectFileResponse,
  ProjectFileUploadResponse,
  ProjectSummary,
  UpdateProjectFilePathPayload,
  UploadProjectFilePayload,
} from '@/modules/project/types'
import { hashProjectFile } from '@/modules/project/project-update'

const projects: ProjectDetail[] = [
  {
    id: 1,
    name: 'PM-Agent 平台 MVP',
    code: 'PM-MVP',
    description: '完成登录、项目、任务和看板最小闭环，为后续 Agent 能力提供真实业务数据。',
    ownerName: '宁宁',
    status: 'running',
    startDate: '2026-06-01',
    endDate: '2026-07-15',
    taskTotal: 6,
    doneTaskTotal: 1,
    memberTotal: 1,
    riskTotal: 0,
  },
]

export async function mockListProjects(): Promise<ProjectSummary[]> {
  return projects
}

export async function mockGetProjectDetail(id: number): Promise<ProjectDetail> {
  const project = projects.find((item) => item.id === id)

  if (!project) {
    throw new Error('项目不存在')
  }

  return project
}

export async function mockCreateProject(payload: CreateProjectRequest): Promise<ProjectDetail> {
  const project: ProjectDetail = {
    id: projects.length + 1,
    name: payload.name,
    code: payload.code,
    description: payload.description,
    ownerName: '宁宁',
    status: 'not_started',
    startDate: payload.startDate ?? '2026-06-01',
    endDate: payload.endDate ?? '2026-07-15',
    taskTotal: 0,
    doneTaskTotal: 0,
    memberTotal: 1,
    riskTotal: 0,
  }

  projects.unshift(project)
  return project
}

let mockFileId = 1
const projectFiles = new Map<number, ProjectFileResponse[]>()

export async function mockUploadProjectFile(
  projectId: number,
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

export async function mockListProjectFiles(projectId: number): Promise<ProjectFileResponse[]> {
  return [...(projectFiles.get(projectId) ?? [])]
}

export async function mockOverwriteProjectFile(
  projectId: number,
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
  projectId: number,
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
  projectId: number,
  fileId: number,
  _lockVersion: number,
): Promise<void> {
  const files = projectFiles.get(projectId) ?? []
  projectFiles.set(
    projectId,
    files.filter((file) => file.id !== fileId),
  )
}

export async function mockRequestProjectFileParsing(): Promise<void> {}

function requireMockFile(projectId: number, fileId: number) {
  const file = (projectFiles.get(projectId) ?? []).find((item) => item.id === fileId)
  if (!file) throw new Error('项目文件不存在')
  return file
}
