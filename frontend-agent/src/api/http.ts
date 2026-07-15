import axios from 'axios'
import { createRequestId } from '@/shared/utils/request-id'

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 60_000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('pm-agent-token') || import.meta.env.VITE_PM_AGENT_TOKEN
  if (token) {
    config.headers.Authorization = token.startsWith('Bearer ') ? token : `Bearer ${token}`
  }
  config.headers['X-Trace-Id'] ||= createRequestId().replaceAll('-', '')
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.message || error.response?.data?.detail || '请求失败，请稍后重试'
    return Promise.reject(Object.assign(error, { userMessage: message }))
  },
)
