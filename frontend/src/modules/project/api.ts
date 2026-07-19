import { request } from '@/api/http'
import { useMock } from '@/mock'
import {
  mockCreateProject,
  mockGetProjectDetail,
  mockListProjects,
  mockUploadProjectFileBatch,
} from '@/modules/project/mock'
import type {
  CreateProjectRequest,
  ProjectDetail,
  ProjectFileUploadBatchResponse,
  ProjectSummary,
  UploadProjectFileBatchPayload,
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

export async function uploadProjectFileBatch(
  projectId: number,
  payload: UploadProjectFileBatchPayload,
) {
  if (useMock) {
    return mockUploadProjectFileBatch(payload)
  }

  const formData = new FormData()
  formData.append(
    'manifest',
    new Blob([JSON.stringify(payload.manifest)], { type: 'application/json' }),
    'manifest.json',
  )
  formData.append(
    'batch',
    new Blob([JSON.stringify(payload.batch)], { type: 'application/json' }),
    'batch.json',
  )
  payload.files.forEach((file) => formData.append('files', file, file.name))

  return request<ProjectFileUploadBatchResponse>({
    url: `/api/v1/projects/${projectId}/file-ingest-batches/concurrent-uploads`,
    method: 'post',
    data: formData,
    headers: {
      'X-Idempotency-Key': payload.batch.idempotencyKey,
    },
    timeout: 10 * 60 * 1000,
  })
}
