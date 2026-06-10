export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  displayName: string
  email?: string
  mobile?: string
}

export interface UserProfile {
  id: number
  tenantId: number
  username: string
  displayName: string
  email?: string | null
  mobile?: string | null
  status?: string | null
  lastLoginAt?: string | null
}

export interface AuthTokenResponse {
  tokenName: string
  tokenValue: string
  user: UserProfile
}

export type LoginResponse = AuthTokenResponse
