import { defineStore } from 'pinia'
import { getCurrentUser, login, logout, register } from '@/modules/auth/api'
import type { AuthTokenResponse, LoginRequest, RegisterRequest, UserProfile } from '@/modules/auth/types'

const tokenStorageKey = 'pm-agent-token'

interface AuthState {
  token: string
  user: UserProfile | null
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: localStorage.getItem(tokenStorageKey) ?? '',
    user: null,
  }),
  actions: {
    applyAuthResult(result: AuthTokenResponse) {
      this.token = result.tokenValue
      this.user = result.user
      localStorage.setItem(tokenStorageKey, result.tokenValue)
    },
    async login(payload: LoginRequest) {
      const result = await login(payload)
      this.applyAuthResult(result)
    },
    async register(payload: RegisterRequest) {
      const result = await register(payload)
      this.applyAuthResult(result)
    },
    async loadCurrentUser() {
      this.user = await getCurrentUser()
    },
    clearAuth() {
      this.token = ''
      this.user = null
      localStorage.removeItem(tokenStorageKey)
    },
    async logout() {
      try {
        if (this.token) {
          await logout()
        }
      } finally {
        this.clearAuth()
      }
    },
  },
})
