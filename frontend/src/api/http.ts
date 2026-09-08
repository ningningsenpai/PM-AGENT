import axios, { type AxiosRequestConfig } from 'axios'
import { useMessage } from 'naive-ui'
import type { ApiResponse } from '@/shared/types/api'
import { createTraceId } from '@/shared/utils/request-id'

export type RequestConfig = AxiosRequestConfig

export class RequestError extends Error {
  constructor(message: string, public code?: number, public traceId?: string, public uncertain = false) {
    super(traceId ? `${message}（追踪编号：${traceId}）` : message)
    this.name = 'RequestError'
  }
}

let unauthorizedHandler: (() => void) | undefined
export function onUnauthorized(handler: () => void) { unauthorizedHandler = handler }

function notifyUnauthorized(code?: number, authorization?: unknown) {
  if (code === 20001 && authorization === `Bearer ${localStorage.getItem('pm-agent-token')}`) unauthorizedHandler?.()
}

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
      notifyUnauthorized(body.code, response.config.headers.get('Authorization'))
      return Promise.reject(new RequestError(body.message || '请求失败', body.code, body.traceId))
    }

    return response
  },
  (error) => {
    if (axios.isCancel(error)) return Promise.reject(error)
    const body = error?.response?.data
    notifyUnauthorized(error?.response?.status === 401 ? 20001 : body?.code, error?.config?.headers?.get?.('Authorization'))
    const message = body?.message || (error?.code === 'ECONNABORTED' ? '请求超时，请先确认处理结果' : '连接服务失败，请稍后重试')
    return Promise.reject(new RequestError(message, body?.code, body?.traceId, !error?.response || error.response.status >= 500))
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
