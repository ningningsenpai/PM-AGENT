import type { ApiResponse } from '@/shared/types/api'

export function ok<T>(data: T): ApiResponse<T> {
  return {
    code: 0,
    message: '成功',
    data,
    traceId: 'mocktraceid',
  }
}

export const useMock = import.meta.env.VITE_USE_MOCK === 'true'
