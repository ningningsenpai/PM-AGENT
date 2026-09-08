import type { AuthTokenResponse, LoginRequest, RegisterRequest, UserProfile } from '@/modules/auth/types'

const user: UserProfile = {
  id: '1',
  username: 'admin',
  email: 'admin@pm-agent.local',
  status: 'enabled',
  lastLoginAt: '2026-06-09T09:00:00',
}

function createAuthResponse(profile: UserProfile): AuthTokenResponse {
  return {
    tokenName: 'Authorization',
    tokenValue: 'mock-token',
    user: profile,
  }
}

export async function mockLogin(payload: LoginRequest): Promise<AuthTokenResponse> {
  if (!payload.email || !payload.password) {
    throw new Error('请输入邮箱和密码')
  }

  return createAuthResponse(user)
}

export async function mockRegister(payload: RegisterRequest): Promise<AuthTokenResponse> {
  if (!payload.username || !payload.password || !payload.email) {
    throw new Error('请输入用户名、邮箱和密码')
  }

  return createAuthResponse({
    ...user,
    id: '2',
    username: payload.username,
    email: payload.email,
    lastLoginAt: null,
  })
}

export async function mockMe(): Promise<UserProfile> {
  return user
}

export async function mockLogout(): Promise<void> {
  return undefined
}
