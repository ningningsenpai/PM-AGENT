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
    url: `/api/v1/projects/${projectId}/files/parse/init`,
    method: 'post',
  })
}
