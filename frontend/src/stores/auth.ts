import { defineStore } from 'pinia'
import { getCurrentUser, login, logout, register, updateCurrentUser } from '@/modules/auth/api'
import type { AuthTokenResponse, LoginRequest, RegisterRequest, UserProfile, UpdateUserProfileRequest } from '@/modules/auth/types'

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
      const token = this.token
      const user = await getCurrentUser()
      if (token === this.token) this.user = user
    },
    async updateCurrentUser(payload: UpdateUserProfileRequest) {
      const token = this.token
      const user = await updateCurrentUser(payload)
      if (token === this.token) this.user = user
    },
    clearAuth() {
      this.token = ''
      this.user = null
      localStorage.removeItem(tokenStorageKey)
      Object.keys(sessionStorage).filter((key) => key.startsWith('pm-operation:') || key.startsWith('pm-context-edit:')).forEach((key) => sessionStorage.removeItem(key))
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
