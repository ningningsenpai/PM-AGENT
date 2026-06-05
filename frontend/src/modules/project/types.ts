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
