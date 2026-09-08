import type { CreateTaskRequest, TaskItem, UpdateTaskStatusRequest } from '@/modules/task/types'

const tasks: TaskItem[] = [
  {
    id: 1,
    projectId: '1',
    title: '初始化前端工程骨架',
    description: '创建 Vite、Vue Router、Pinia、Axios 与 Naive UI 基础结构。',
    assigneeName: '宁宁',
    status: 'done',
    priority: 'p1',
    dueDate: '2026-06-06',
    estimatedHours: 4,
  },
  {
    id: 2,
    projectId: '1',
    title: '准备 MySQL Docker 容器',
    description: '创建 deploy 目录、Docker Compose 与环境变量示例。',
    assigneeName: '宁宁',
    status: 'developing',
    priority: 'p1',
    dueDate: '2026-06-07',
    estimatedHours: 2,
  },
  {
    id: 3,
    projectId: '1',
    title: '设计任务状态流转接口',
    description: '实现状态校验并写入任务状态日志。',
    assigneeName: '宁宁',
    status: 'pending',
    priority: 'p0',
    dueDate: '2026-06-08',
    estimatedHours: 5,
  },
  {
    id: 4,
    projectId: '1',
    title: '联调项目列表页面',
    description: '从 Mock 数据切换到真实接口后验证项目列表。',
    assigneeName: '宁宁',
    status: 'testing',
    priority: 'p2',
    dueDate: '2026-06-10',
    estimatedHours: 3,
  },
]

export async function mockListTasks(projectId: string): Promise<TaskItem[]> {
  return tasks.filter((item) => item.projectId === projectId)
}

export async function mockCreateTask(payload: CreateTaskRequest): Promise<TaskItem> {
  const task: TaskItem = {
    id: tasks.length + 1,
    projectId: payload.projectId,
    title: payload.title,
    description: payload.description,
    assigneeName: '宁宁',
    status: 'pending',
    priority: payload.priority,
    dueDate: payload.dueDate,
    estimatedHours: payload.estimatedHours,
  }

  tasks.unshift(task)
  return task
}

export async function mockUpdateTaskStatus(id: number, payload: UpdateTaskStatusRequest): Promise<TaskItem> {
  const task = tasks.find((item) => item.id === id)

  if (!task) {
    throw new Error('任务不存在')
  }

  task.status = payload.status
  return task
}
