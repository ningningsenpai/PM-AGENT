export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  traceId: string
}

export interface PageResult<T> {
  records: T[]
  total: number
}
