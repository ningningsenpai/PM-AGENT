export interface LoginRequest {
  username: string
  password: string
}

export interface UserProfile {
  id: number
  username: string
  displayName: string
  email?: string
}

export interface LoginResponse {
  token: string
  user: UserProfile
}
