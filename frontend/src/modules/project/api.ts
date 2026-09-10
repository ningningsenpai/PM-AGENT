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
  ProjectFileParseRecovery,
  ProjectFileSyncPlan,
  ProjectFileSyncPlanRequest,
  ProjectFileUploadResponse,
  ProjectSummary,
  UpdateProjectFilePathPayload,
  UploadProjectFilePayload,
} from '@/modules/project/types'

export async function listProjects() {
  if (useMock) {
    return mockListProjects()
  }

  const projects = await request<ProjectSummary[]>({
    url: '/api/v1/projects',
    method: 'get',
  })
  return projects
}

export async function getProjectDetail(id: string) {
  if (useMock) {
    return mockGetProjectDetail(id)
  }

  const project = await request<ProjectDetail>({
    url: `/api/v1/projects/${id}`,
    method: 'get',
  })
  return project
}

export async function createProject(payload: CreateProjectRequest) {
  if (useMock) {
    return mockCreateProject(payload)
  }

  const project = await request<ProjectDetail>({
    url: '/api/v1/projects',
    method: 'post',
    data: payload,
  })
  return project
}

export async function uploadProjectFile(projectId: string, payload: UploadProjectFilePayload) {
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

export async function listProjectFiles(projectId: string, signal?: AbortSignal) {
  if (useMock) {
    return mockListProjectFiles(projectId)
  }

  return request<ProjectFileResponse[]>({
    url: `/api/v1/projects/${projectId}/files`,
    method: 'get',
    params: { businessCode: 'project' },
    signal,
  })
}

export async function overwriteProjectFile(
  projectId: string,
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
  projectId: string,
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
  projectId: string,
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
  projectId: string,
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

export async function requestProjectFileParsing(
  projectId: string,
  fileIds: number[] | undefined,
  idempotencyKey: string,
) {
  if (useMock) {
    return mockRequestProjectFileParsing(projectId)
  }

  return request<ProjectFileParseResult>({
    url: `/api/v1/projects/${projectId}/files/parse/init`,
    method: 'post',
    params: { force: Boolean(fileIds?.length) },
    data: fileIds?.length ? { fileIds } : undefined,
    headers: { 'X-Idempotency-Key': idempotencyKey },
    // 传输超时只转入原幂等键恢复，不代表服务端解析已停止。
    timeout: 2 * 60 * 1000,
  })
}

export async function recoverProjectFileParsing(projectId: string, idempotencyKey: string) {
  if (useMock) {
    const serverTime = new Intl.DateTimeFormat('sv-SE', {
      dateStyle: 'short',
      timeStyle: 'medium',
      hour12: false,
      timeZone: 'Asia/Shanghai',
    }).format(new Date()).replace(' ', 'T') + '+08:00'
    return {
      runId: null,
      status: 'absent',
      retryable: true,
      retryMode: 'same_key',
      leaseUntil: null,
      serverTime,
      result: null,
      error: null,
    } satisfies ProjectFileParseRecovery
  }

  return request<ProjectFileParseRecovery>({
    url: `/api/v1/projects/${projectId}/files/parse/recover`,
    method: 'post',
    headers: { 'X-Idempotency-Key': idempotencyKey },
  })
}

export async function deleteProject(projectId: string) {
  if (useMock) throw new Error('演示模式不支持删除项目')
  return request<void>({ url: `/api/v1/projects/${projectId}`, method: 'delete' })
}

export async function getFileReadUrl(projectId: string, fileId: number) {
  if (useMock) throw new Error('演示文件没有可读取的原文')
  return request<{ fileId: number; fileName: string; url: string; expiresAt: string }>({
    url: `/api/v1/projects/${projectId}/files/${fileId}/read-url`, method: 'get',
  })
}
