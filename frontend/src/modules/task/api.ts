import { useMock } from '@/mock'
import { mockCreateTask, mockListTasks, mockUpdateTaskStatus } from '@/modules/task/mock'
import type { CreateTaskRequest, TaskItem, UpdateTaskStatusRequest } from '@/modules/task/types'

export async function listTasks(projectId: string): Promise<TaskItem[]> {
  if (useMock) return mockListTasks(projectId)
  throw new Error('任务管理暂未开放')
}

export async function createTask(payload: CreateTaskRequest): Promise<TaskItem> {
  if (useMock) return mockCreateTask(payload)
  throw new Error('任务创建暂未开放')
}

export async function updateTaskStatus(id: number, payload: UpdateTaskStatusRequest): Promise<TaskItem> {
  if (useMock) return mockUpdateTaskStatus(id, payload)
  throw new Error('任务状态流转暂未开放')
}
