export interface Student {
  id: number
  studentNo: string
  name: string
  gender: 'MALE' | 'FEMALE'
  grade: string
  phone: string | null
  email: string | null
  status: 'ACTIVE' | 'INACTIVE'
  createdAt: string
}

export interface CreateStudentRequest {
  studentNo: string
  name: string
  gender: 'MALE' | 'FEMALE'
  grade: string
  phone: string
  email: string
}

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  traceId: string
}

