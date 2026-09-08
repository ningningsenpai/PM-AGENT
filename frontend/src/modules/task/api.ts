import { request } from '@/api/http'
import { useMock } from '@/mock'
import { mockCreateTask, mockListTasks, mockUpdateTaskStatus } from '@/modules/task/mock'
import type { CreateTaskRequest, TaskItem, UpdateTaskStatusRequest } from '@/modules/task/types'

export async function listTasks(projectId: string) {
  if (useMock) {
    return mockListTasks(projectId)
  }

  return request<TaskItem[]>({
    url: '/api/v1/tasks',
    method: 'get',
    params: { projectId },
  })
}

export async function createTask(payload: CreateTaskRequest) {
  if (useMock) {
    return mockCreateTask(payload)
  }

  return request<TaskItem>({
    url: '/api/v1/tasks',
    method: 'post',
    data: payload,
  })
}

export async function updateTaskStatus(id: number, payload: UpdateTaskStatusRequest) {
  if (useMock) {
    return mockUpdateTaskStatus(id, payload)
  }

  return request<TaskItem>({
    url: `/api/v1/tasks/${id}/status`,
    method: 'put',
    data: payload,
  })
}
