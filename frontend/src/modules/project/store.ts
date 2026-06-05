import { defineStore } from 'pinia'
import { listProjects } from '@/modules/project/api'
import type { ProjectSummary } from '@/modules/project/types'

interface ProjectState {
  projects: ProjectSummary[]
  loading: boolean
}

export const useProjectStore = defineStore('project', {
  state: (): ProjectState => ({
    projects: [],
    loading: false,
  }),
  actions: {
    async loadProjects() {
      this.loading = true
      try {
        this.projects = await listProjects()
      } finally {
        this.loading = false
      }
    },
  },
})
