import { request } from '@/api/http'
import { useMock } from '@/mock'
import {
  mockCreateProject,
  mockGetProjectDetail,
  mockListProjects,
  mockRequestProjectFileParsing,
  mockUploadProjectFile,
} from '@/modules/project/mock'
import type {
  CreateProjectRequest,
  ProjectDetail,
  ProjectFileUploadResponse,
  ProjectSummary,
  UploadProjectFilePayload,
} from '@/modules/project/types'

export async function listProjects() {
  if (useMock) {
    return mockListProjects()
  }

  return request<ProjectSummary[]>({
    url: '/api/v1/projects',
    method: 'get',
  })
}

export async function getProjectDetail(id: number) {
  if (useMock) {
    return mockGetProjectDetail(id)
  }

  return request<ProjectDetail>({
    url: `/api/v1/projects/${id}`,
    method: 'get',
  })
}

export async function createProject(payload: CreateProjectRequest) {
  if (useMock) {
    return mockCreateProject(payload)
  }

  return request<ProjectDetail>({
    url: '/api/v1/projects',
    method: 'post',
    data: payload,
  })
}

export async function uploadProjectFile(projectId: number, payload: UploadProjectFilePayload) {
  if (useMock) {
    return mockUploadProjectFile(payload)
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

export async function requestProjectFileParsing(projectId: number) {
  if (useMock) {
    return mockRequestProjectFileParsing()
  }

  return request<void>({
    url: `/api/v1/projects/${projectId}/files/parse`,
    method: 'post',
  })
}
