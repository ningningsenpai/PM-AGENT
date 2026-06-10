import type { AuthTokenResponse, LoginRequest, RegisterRequest, UserProfile } from '@/modules/auth/types'

const user: UserProfile = {
  id: 1,
  tenantId: 0,
  username: 'admin',
  displayName: '宁宁',
  email: 'admin@pm-agent.local',
  mobile: '13800000000',
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
  if (!payload.username || !payload.password) {
    throw new Error('请输入用户名和密码')
  }

  return createAuthResponse(user)
}

export async function mockRegister(payload: RegisterRequest): Promise<AuthTokenResponse> {
  if (!payload.username || !payload.password || !payload.displayName) {
    throw new Error('请输入用户名、展示名称和密码')
  }

  return createAuthResponse({
    ...user,
    id: 2,
    username: payload.username,
    displayName: payload.displayName,
    email: payload.email || null,
    mobile: payload.mobile || null,
    lastLoginAt: null,
  })
}

export async function mockMe(): Promise<UserProfile> {
  return user
}

export async function mockLogout(): Promise<void> {
  return undefined
}
