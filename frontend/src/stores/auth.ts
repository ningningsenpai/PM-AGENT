import { defineStore } from 'pinia'
import { login, getCurrentUser } from '@/modules/auth/api'
import type { LoginRequest, UserProfile } from '@/modules/auth/types'

interface AuthState {
  token: string
  user: UserProfile | null
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: localStorage.getItem('pm-agent-token') ?? '',
    user: null,
  }),
  actions: {
    async login(payload: LoginRequest) {
      const result = await login(payload)
      this.token = result.token
      this.user = result.user
      localStorage.setItem('pm-agent-token', result.token)
    },
    async loadCurrentUser() {
      this.user = await getCurrentUser()
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('pm-agent-token')
    },
  },
})
