import type { LoginRequest, LoginResponse, UserProfile } from '@/modules/auth/types'
import { request } from '@/api/http'
import { useMock } from '@/mock'
import { mockLogin, mockMe } from '@/modules/auth/mock'

export async function login(payload: LoginRequest) {
  if (useMock) {
    return mockLogin(payload)
  }

  return request<LoginResponse>({
    url: '/api/v1/auth/login',
    method: 'post',
    data: payload,
  })
}

export async function getCurrentUser() {
  if (useMock) {
    return mockMe()
  }

  return request<UserProfile>({
    url: '/api/v1/auth/me',
    method: 'get',
  })
}
