export type TaskStatus = 'pending' | 'developing' | 'integrating' | 'testing' | 'done' | 'cancelled'
export type TaskPriority = 'p0' | 'p1' | 'p2' | 'p3'

export interface TaskItem {
  id: number
  projectId: string
  title: string
  description?: string
  assigneeName?: string
  status: TaskStatus
  priority: TaskPriority
  dueDate?: string
  estimatedHours?: number
}

export interface CreateTaskRequest {
  projectId: string
  title: string
  description?: string
  assigneeId?: number
  priority: TaskPriority
  dueDate?: string
  estimatedHours?: number
}

export interface UpdateTaskStatusRequest {
  status: TaskStatus
  reason?: string
}

export const taskStatusOptions: Array<{ label: string; value: TaskStatus; tone: string }> = [
  { label: '待处理', value: 'pending', tone: '#94a3b8' },
  { label: '开发中', value: 'developing', tone: '#2563eb' },
  { label: '待联调', value: 'integrating', tone: '#7c3aed' },
  { label: '待测试', value: 'testing', tone: '#f59e0b' },
  { label: '已完成', value: 'done', tone: '#16a34a' },
  { label: '已取消', value: 'cancelled', tone: '#64748b' },
]
