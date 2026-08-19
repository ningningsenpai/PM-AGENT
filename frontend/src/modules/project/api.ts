import { request } from '@/api/http'
import { useMock } from '@/mock'
import {
  mockCreateProject,
  mockDeleteProjectFile,
  mockGetProjectDetail,
  mockListProjectFiles,
  mockListProjects,
  mockOverwriteProjectFile,
  mockPlanProjectFileSync,
  mockRequestProjectFileParsing,
  mockUpdateProjectFilePath,
  mockUploadProjectFile,
} from '@/modules/project/mock'
import type {
  CreateProjectRequest,
  OverwriteProjectFilePayload,
  ProjectDetail,
  ProjectFileResponse,
  ProjectFileParseResult,
  ProjectFileSyncPlan,
  ProjectFileSyncPlanRequest,
  ProjectFileUploadResponse,
  ProjectSummary,
  UpdateProjectFilePathPayload,
  UploadProjectFilePayload,
} from '@/modules/project/types'

interface ProjectApiResponse {
  id: number
  projectName: string
  status: 'initializing' | 'active' | 'init_failed'
  createdAt: string
  updatedAt: string
}

function toProjectSummary(project: ProjectApiResponse): ProjectSummary {
  const statusMap = {
    initializing: 'not_started',
    active: 'running',
    init_failed: 'paused',
  } as const
  return {
    id: project.id,
    name: project.projectName,
    ownerName: '当前用户',
    status: statusMap[project.status],
    startDate: project.createdAt,
    endDate: project.updatedAt,
    taskTotal: 0,
    doneTaskTotal: 0,
  }
}

function toProjectDetail(project: ProjectApiResponse): ProjectDetail {
  return {
    ...toProjectSummary(project),
    memberTotal: 1,
    riskTotal: 0,
  }
}

export async function listProjects() {
  if (useMock) {
    return mockListProjects()
  }

  const projects = await request<ProjectApiResponse[]>({
    url: '/api/v1/projects',
    method: 'get',
  })
  return projects.map(toProjectSummary)
}

export async function getProjectDetail(id: number) {
  if (useMock) {
    return mockGetProjectDetail(id)
  }

  const project = await request<ProjectApiResponse>({
    url: `/api/v1/projects/${id}`,
    method: 'get',
  })
  return toProjectDetail(project)
}

export async function createProject(payload: CreateProjectRequest) {
  if (useMock) {
    return mockCreateProject(payload)
  }

  const project = await request<ProjectApiResponse>({
    url: '/api/v1/projects',
    method: 'post',
    data: { projectName: payload.name },
  })
  return toProjectDetail(project)
}

export async function uploadProjectFile(projectId: number, payload: UploadProjectFilePayload) {
  if (useMock) {
    return mockUploadProjectFile(projectId, payload)
  }

  const formData = new FormData()
  formData.append('file', payload.file, payload.file.name)
  formData.append('relativePath', payload.relativePath)
  formData.append('sourceMtimeMs', String(payload.sourceMtimeMs))

  return request<ProjectFileUploadResponse>({
    url: `/api/v1/projects/${projectId}/files`,
    method: 'post',
    data: formData,
    headers: {
      'X-Idempotency-Key': payload.idempotencyKey,
    },
    timeout: 2 * 60 * 1000,
  })
}

export async function listProjectFiles(projectId: number) {
  if (useMock) {
    return mockListProjectFiles(projectId)
  }

  return request<ProjectFileResponse[]>({
    url: `/api/v1/projects/${projectId}/files`,
    method: 'get',
    params: { businessCode: 'project' },
  })
}

export async function overwriteProjectFile(
  projectId: number,
  payload: OverwriteProjectFilePayload,
) {
  if (useMock) {
    return mockOverwriteProjectFile(projectId, payload)
  }

  const formData = new FormData()
  formData.append('file', payload.file, payload.file.name)
  formData.append('sourceMtimeMs', String(payload.sourceMtimeMs))
  formData.append('lockVersion', String(payload.lockVersion))

  return request<ProjectFileResponse>({
    url: `/api/v1/projects/${projectId}/files/${payload.fileId}/content`,
    method: 'put',
    data: formData,
    headers: {
      'X-Idempotency-Key': payload.idempotencyKey,
    },
    timeout: 2 * 60 * 1000,
  })
}

export async function updateProjectFilePath(
  projectId: number,
  payload: UpdateProjectFilePathPayload,
) {
  if (useMock) {
    return mockUpdateProjectFilePath(projectId, payload)
  }

  return request<ProjectFileResponse>({
    url: `/api/v1/projects/${projectId}/files/${payload.fileId}/path`,
    method: 'patch',
    data: {
      relativePath: payload.relativePath,
      sourceMtimeMs: payload.sourceMtimeMs,
      lockVersion: payload.lockVersion,
    },
  })
}

export async function deleteProjectFile(
  projectId: number,
  fileId: number,
  lockVersion: number,
) {
  if (useMock) {
    return mockDeleteProjectFile(projectId, fileId, lockVersion)
  }

  return request<void>({
    url: `/api/v1/projects/${projectId}/files/${fileId}`,
    method: 'delete',
    params: { lockVersion },
  })
}

export async function planProjectFileSync(
  projectId: number,
  payload: ProjectFileSyncPlanRequest,
) {
  if (useMock) {
    return mockPlanProjectFileSync(projectId, payload)
  }

  return request<ProjectFileSyncPlan>({
    url: `/api/v1/projects/${projectId}/files/sync/plan`,
    method: 'post',
    data: payload,
  })
}

export async function requestProjectFileParsing(projectId: number) {
  if (useMock) {
    return mockRequestProjectFileParsing(projectId)
  }

  return request<ProjectFileParseResult>({
    url: `/api/v1/projects/${projectId}/files/parse/init`,
    method: 'post',
    // 文件解析包含串行模型调用，单次模型超时由服务端配置控制。
    timeout: 0,
  })
}
