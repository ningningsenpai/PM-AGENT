import type { LoginRequest, LoginResponse, UserProfile } from '@/modules/auth/types'

const user: UserProfile = {
  id: 1,
  username: 'admin',
  displayName: '宁宁',
  email: 'admin@pm-agent.local',
}

export async function mockLogin(payload: LoginRequest): Promise<LoginResponse> {
  if (!payload.username || !payload.password) {
    throw new Error('请输入用户名和密码')
  }

  return {
    token: 'mock-token',
    user,
  }
}

export async function mockMe(): Promise<UserProfile> {
  return user
}
