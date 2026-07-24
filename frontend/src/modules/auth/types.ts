export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  email: string
}

export interface UserProfile {
  id: number
  username: string
  email: string
  status: string
  lastLoginAt?: string | null
}

export interface AuthTokenResponse {
  tokenName: string
  tokenValue: string
  user: UserProfile
}

export type LoginResponse = AuthTokenResponse
