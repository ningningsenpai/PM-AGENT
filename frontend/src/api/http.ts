import axios, { type AxiosRequestConfig } from 'axios'
import { useMessage } from 'naive-ui'
import type { ApiResponse } from '@/shared/types/api'
import { createTraceId } from '@/shared/utils/request-id'

export type RequestConfig = AxiosRequestConfig

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 15000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('pm-agent-token')
  config.headers.set('X-Trace-Id', createTraceId())

  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }

  return config
})

http.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResponse<unknown>

    if (body.code !== 0) {
      return Promise.reject(new Error(`${body.message}（traceId: ${body.traceId}）`))
    }

    return response
  },
  (error) => {
    const message = error?.response?.data?.message || error?.message || '请求失败，请稍后重试'
    return Promise.reject(new Error(message))
  },
)

export async function request<T>(config: RequestConfig): Promise<T> {
  const response = await http.request<ApiResponse<T>>(config)
  return response.data.data
}

export function showRequestError(error: unknown) {
  const message = useMessage()
  message.error(error instanceof Error ? error.message : '操作失败，请稍后重试')
}
