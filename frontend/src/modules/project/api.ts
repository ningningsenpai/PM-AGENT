import { request } from '@/api/http'
import { useMock } from '@/mock'
import { mockCreateProject, mockGetProjectDetail, mockListProjects } from '@/modules/project/mock'
import type { CreateProjectRequest, ProjectDetail, ProjectSummary } from '@/modules/project/types'

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
