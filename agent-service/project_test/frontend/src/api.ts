import type { ApiResponse, CreateStudentRequest, Student } from './types'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  const result = (await response.json()) as ApiResponse<T>
  if (!response.ok || result.code !== 0) {
    throw new Error(`${result.message}（追踪号：${result.traceId}）`)
  }
  return result.data
}

/** 查询学生档案列表，可按姓名关键字筛选。 */
export function listStudents(name = ''): Promise<Student[]> {
  const query = name ? `?name=${encodeURIComponent(name)}` : ''
  return request<Student[]>(`/api/v1/students${query}`)
}

/** 新增一条学生档案。 */
export function createStudent(payload: CreateStudentRequest): Promise<Student> {
  return request<Student>('/api/v1/students', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

