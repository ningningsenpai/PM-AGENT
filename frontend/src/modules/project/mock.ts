import type {
  CreateProjectRequest,
  ProjectDetail,
  ProjectFileUploadResponse,
  ProjectSummary,
  UploadProjectFilePayload,
} from '@/modules/project/types'

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

export async function mockUploadProjectFile(
  payload: UploadProjectFilePayload,
): Promise<ProjectFileUploadResponse> {
  return {
    fileId: mockFileId++,
    relativePath: payload.relativePath,
    fileName: payload.file.name,
    success: true,
    status: 'active',
    uploadStatus: 'success',
    errorCode: null,
    errorMessage: null,
  }
}

export async function mockRequestProjectFileParsing(): Promise<void> {}
