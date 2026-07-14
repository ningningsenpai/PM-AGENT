import { http } from '@/api/http'
import type {
  ApiResponse,
  FileUploadBatchResponse,
  ManifestItem,
  ProjectFileResponse,
  ProjectForm,
  ProjectResponse,
} from './types'

export async function createProject(payload: ProjectForm) {
  const response = await http.post<ApiResponse<ProjectResponse>>('/api/v1/projects', payload)
  return response.data.data
}

export async function createFileUpload(
  projectId: number,
  rootDirectoryName: string,
  files: ManifestItem[],
) {
  const response = await http.post<ApiResponse<FileUploadBatchResponse>>(
    `/api/v1/projects/${projectId}/file-uploads`,
    { rootDirectoryName, sourceType: 'directory_picker', files },
  )
  return response.data.data
}

export async function uploadProjectFile(
  projectId: number,
  uploadId: number,
  relativePath: string,
  file: File,
) {
  const form = new FormData()
  form.append('relativePath', relativePath)
  form.append('lastModifiedEpochMs', String(file.lastModified))
  form.append('file', file, file.name)
  const response = await http.post<ApiResponse<ProjectFileResponse>>(
    `/api/v1/projects/${projectId}/file-uploads/${uploadId}/files`,
    form,
  )
  return response.data.data
}

export async function getFileUpload(projectId: number, uploadId: number) {
  const response = await http.get<ApiResponse<FileUploadBatchResponse>>(
    `/api/v1/projects/${projectId}/file-uploads/${uploadId}`,
  )
  return response.data.data
}

export async function completeFileUpload(projectId: number, uploadId: number) {
  const response = await http.post<ApiResponse<FileUploadBatchResponse>>(
    `/api/v1/projects/${projectId}/file-uploads/${uploadId}/complete`,
    null,
  )
  return response.data.data
}

export async function retryProjectFile(
  projectId: number,
  uploadId: number,
  fileId: number,
) {
  const response = await http.post<ApiResponse<ProjectFileResponse>>(
    `/api/v1/projects/${projectId}/file-uploads/${uploadId}/files/${fileId}/retry`,
    null,
  )
  return response.data.data
}
