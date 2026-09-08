import type { AuthTokenResponse, LoginRequest, RegisterRequest, UserProfile, UpdateUserProfileRequest, ChangePasswordRequest } from '@/modules/auth/types'
import { request } from '@/api/http'
import { useMock } from '@/mock'
import { mockLogin, mockLogout, mockMe, mockRegister } from '@/modules/auth/mock'

export async function login(payload: LoginRequest) {
  if (useMock) {
    return mockLogin(payload)
  }

  return request<AuthTokenResponse>({
    url: '/api/v1/auth/login',
    method: 'post',
    data: payload,
  })
}

export async function register(payload: RegisterRequest) {
  if (useMock) {
    return mockRegister(payload)
  }

  return request<AuthTokenResponse>({
    url: '/api/v1/auth/register',
    method: 'post',
    data: payload,
  })
}

export async function getCurrentUser() {
  if (useMock) {
    return mockMe()
  }

  return request<UserProfile>({
    url: '/api/v1/users/me',
    method: 'get',
  })
}

export async function logout() {
  if (useMock) {
    return mockLogout()
  }

  return request<void>({
    url: '/api/v1/auth/logout',
    method: 'post',
  })
}

export async function updateCurrentUser(payload: UpdateUserProfileRequest) {
  if (useMock) throw new Error('演示模式不支持保存用户资料，请连接真实服务')
  return request<UserProfile>({ url: '/api/v1/users/me', method: 'put', data: payload })
}

export async function changePassword(payload: ChangePasswordRequest) {
  if (useMock) throw new Error('演示模式不支持修改密码，请连接真实服务')
  return request<void>({ url: '/api/v1/users/me/password', method: 'put', data: payload })
}
