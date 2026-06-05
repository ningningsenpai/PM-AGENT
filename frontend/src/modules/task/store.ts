import { defineStore } from 'pinia'
import { listTasks, updateTaskStatus } from '@/modules/task/api'
import type { TaskItem, TaskStatus } from '@/modules/task/types'

interface TaskState {
  tasks: TaskItem[]
  loading: boolean
}

export const useTaskStore = defineStore('task', {
  state: (): TaskState => ({
    tasks: [],
    loading: false,
  }),
  actions: {
    async loadTasks(projectId: number) {
      this.loading = true
      try {
        this.tasks = await listTasks(projectId)
      } finally {
        this.loading = false
      }
    },
    async changeTaskStatus(id: number, status: TaskStatus) {
      const task = await updateTaskStatus(id, { status })
      const index = this.tasks.findIndex((item) => item.id === id)

      if (index >= 0) {
        this.tasks[index] = task
      }
    },
  },
})
