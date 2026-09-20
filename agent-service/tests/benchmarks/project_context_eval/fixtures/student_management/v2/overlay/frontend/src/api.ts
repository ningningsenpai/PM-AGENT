import type { ApiResponse, CreateStudentRequest, Student, UpdateStudentRequest } from './types'

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

export function listStudents(name = ''): Promise<Student[]> {
  const query = name ? `?name=${encodeURIComponent(name)}` : ''
  return request<Student[]>(`/api/v1/students${query}`)
}

export function createStudent(payload: CreateStudentRequest): Promise<Student> {
  return request<Student>('/api/v1/students', { method: 'POST', body: JSON.stringify(payload) })
}

/** v2 已接入学生编辑接口，页面表单将在下一小步接入。 */
export function updateStudent(id: number, payload: UpdateStudentRequest): Promise<Student> {
  return request<Student>(`/api/v1/students/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
}

