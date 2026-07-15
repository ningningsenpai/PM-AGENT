import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  completeFileUpload,
  createFileUpload,
  createProject,
  getFileUpload,
  retryProjectFile,
  uploadProjectFile,
} from './api'
import type {
  FileUploadBatchResponse,
  ManifestItem,
  ProjectFileResponse,
  ProjectForm,
  SelectedDirectory,
  SelectedProjectFile,
} from './types'

export const useProjectUploadStore = defineStore('project-upload', () => {
  const projectId = ref<number | null>(null)
  const upload = ref<FileUploadBatchResponse | null>(null)
  const submitting = ref(false)
  const currentFile = ref('')

  const progress = computed(() => {
    if (!upload.value?.acceptedFileCount) return 0
    const finished = upload.value.uploadedFileCount + upload.value.retryFileCount + upload.value.failedFileCount
    return Math.min(100, Math.round((finished / upload.value.acceptedFileCount) * 100))
  })

  async function submit(form: ProjectForm, directory: SelectedDirectory) {
    submitting.value = true
    try {
      const project = await createProject(form)
      projectId.value = project.id
      const manifest: ManifestItem[] = directory.files.map((item) => ({
        relativePath: item.relativePath,
        sizeBytes: item.file.size,
        lastModifiedEpochMs: item.file.lastModified,
        contentType: item.file.type || 'application/octet-stream',
      }))
      upload.value = await createFileUpload(project.id, directory.name, manifest)
      await uploadWithConcurrency(directory.files.filter((item) => item.uploadAllowed), 3)
      upload.value = await completeFileUpload(project.id, upload.value.id)
    } finally {
      currentFile.value = ''
      submitting.value = false
    }
  }

  async function refresh() {
    if (projectId.value && upload.value) {
      upload.value = await getFileUpload(projectId.value, upload.value.id)
    }
  }

  async function retry(file: ProjectFileResponse) {
    if (!projectId.value || !upload.value) return
    await retryProjectFile(projectId.value, upload.value.id, file.id)
    await refresh()
  }

  function reset() {
    projectId.value = null
    upload.value = null
    submitting.value = false
    currentFile.value = ''
  }

  async function uploadWithConcurrency(files: SelectedProjectFile[], concurrency: number) {
    let cursor = 0
    async function worker() {
      while (cursor < files.length) {
        const index = cursor++
        const item = files[index]
        currentFile.value = item.relativePath
        await uploadWithFrontendRetry(item)
        await refresh()
      }
    }
    await Promise.all(Array.from({ length: Math.min(concurrency, files.length) }, worker))
  }

  async function uploadWithFrontendRetry(item: SelectedProjectFile) {
    if (!projectId.value || !upload.value) return
    const delays = [0, 1000, 3000]
    let lastError: unknown
    for (let attempt = 0; attempt < delays.length; attempt++) {
      if (delays[attempt]) await wait(delays[attempt])
      try {
        await uploadProjectFile(projectId.value, upload.value.id, item.relativePath, item.file)
        return
      } catch (error) {
        lastError = error
        if (!isRetryable(error) || attempt === delays.length - 1) break
      }
    }
    throw lastError
  }

  return { projectId, upload, submitting, currentFile, progress, submit, refresh, retry, reset }
})

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function isRetryable(error: unknown) {
  const candidate = error as { response?: { status?: number }; code?: string }
  if (!candidate.response) return true
  return [502, 503, 504].includes(candidate.response.status || 0)
}
