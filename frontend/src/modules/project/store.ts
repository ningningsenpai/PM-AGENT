import { defineStore } from 'pinia'
import { listProjects } from '@/modules/project/api'
import type { ProjectSummary } from '@/modules/project/types'

interface ProjectState {
  projects: ProjectSummary[]
  loading: boolean
  currentProjectId: string
  error: string
  generation: number
}

export const useProjectStore = defineStore('project', {
  state: (): ProjectState => ({
    projects: [],
    loading: false,
    currentProjectId: '',
    error: '',
    generation: 0,
  }),
  actions: {
    async loadProjects() {
      const generation = ++this.generation
      const token = localStorage.getItem('pm-agent-token')
      this.loading = true
      this.error = ''
      try {
        const projects = await listProjects()
        if (generation !== this.generation || token !== localStorage.getItem('pm-agent-token')) return
        this.projects = projects
        if (!projects.some((p) => p.id === this.currentProjectId)) this.currentProjectId = projects[0]?.id || ''
      } catch (error) {
        if (generation === this.generation) this.error = error instanceof Error ? error.message : '项目加载失败'
      } finally {
        if (generation === this.generation) this.loading = false
      }
    },
  },
})
