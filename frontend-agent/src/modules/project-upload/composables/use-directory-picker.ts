import { ref } from 'vue'
import type { SelectedDirectory, SelectedProjectFile } from '../types'

const MAX_FILE_COUNT = 5000
const MAX_FILE_SIZE = 50 * 1024 * 1024
const MAX_TOTAL_SIZE = 1024 * 1024 * 1024
const SKIP_DIRECTORIES = new Set([
  '.git', '.idea', '.vscode', 'node_modules', 'dist', 'build', 'target', 'out', 'coverage',
  '.venv', 'venv', '__pycache__', '.pytest_cache', '.mypy_cache', '.gradle', '.mvn',
])
const SECRET_SUFFIXES = ['.pem', '.key', '.p12', '.jks', '.crt']
const NON_ANALYZABLE_SUFFIXES = [
  '.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.rar', '.7z', '.tar', '.gz',
]

interface DirectoryHandle {
  name: string
  values(): AsyncIterableIterator<FileHandle | DirectoryHandle>
  kind: 'directory'
}

interface FileHandle {
  name: string
  kind: 'file'
  getFile(): Promise<File>
}

export function useDirectoryPicker() {
  const selectedDirectory = ref<SelectedDirectory | null>(null)
  const selecting = ref(false)

  async function selectDirectory() {
    selecting.value = true
    try {
      const picker = (window as typeof window & {
        showDirectoryPicker?: () => Promise<DirectoryHandle>
      }).showDirectoryPicker
      if (picker) {
        const handle = await picker()
        const files: SelectedProjectFile[] = []
        await collectFiles(handle, '', files)
        selectedDirectory.value = buildSelection(handle.name, files)
        return
      }
      openInputPicker()
    } catch (error) {
      if ((error as DOMException).name !== 'AbortError') {
        throw error
      }
    } finally {
      selecting.value = false
    }
  }

  function clearDirectory() {
    selectedDirectory.value = null
  }

  function selectFromInput(fileList: FileList) {
    const files = Array.from(fileList).map((file) => {
      const browserFile = file as File & { webkitRelativePath?: string }
      const rawPath = browserFile.webkitRelativePath || file.name
      const segments = rawPath.split('/')
      const relativePath = segments.length > 1 ? segments.slice(1).join('/') : rawPath
      return classify(file, relativePath)
    })
    const first = Array.from(fileList)[0] as (File & { webkitRelativePath?: string }) | undefined
    const rootName = first?.webkitRelativePath?.split('/')[0] || '已选择目录'
    selectedDirectory.value = buildSelection(rootName, files)
  }

  function openInputPicker() {
    const input = document.createElement('input')
    input.type = 'file'
    input.multiple = true
    input.setAttribute('webkitdirectory', '')
    input.addEventListener('change', () => {
      if (input.files?.length) selectFromInput(input.files)
    }, { once: true })
    input.click()
  }

  return { selectedDirectory, selecting, selectDirectory, clearDirectory }
}

async function collectFiles(handle: DirectoryHandle, prefix: string, result: SelectedProjectFile[]) {
  for await (const entry of handle.values()) {
    const relativePath = prefix ? `${prefix}/${entry.name}` : entry.name
    if (entry.kind === 'directory') {
      await collectFiles(entry, relativePath, result)
    } else {
      result.push(classify(await entry.getFile(), relativePath))
    }
  }
}

function classify(file: File, relativePath: string): SelectedProjectFile {
  const lower = relativePath.toLowerCase()
  if (lower.split('/').some((segment) => SKIP_DIRECTORIES.has(segment))) {
    return { file, relativePath, uploadAllowed: false, analysisEligible: false, reason: '忽略目录' }
  }
  const name = file.name.toLowerCase()
  if (name === '.env' || name.startsWith('.env.') || SECRET_SUFFIXES.some((suffix) => name.endsWith(suffix))) {
    return { file, relativePath, uploadAllowed: false, analysisEligible: false, reason: '敏感文件' }
  }
  const analysisEligible = !NON_ANALYZABLE_SUFFIXES.some((suffix) => name.endsWith(suffix))
  return {
    file,
    relativePath,
    uploadAllowed: true,
    analysisEligible,
    reason: analysisEligible ? undefined : '仅上传，不参与解析',
  }
}

function buildSelection(name: string, files: SelectedProjectFile[]): SelectedDirectory {
  if (files.length > MAX_FILE_COUNT) throw new Error('单次目录文件数量不能超过 5000 个')
  if (files.some((item) => item.file.size > MAX_FILE_SIZE)) throw new Error('单个文件大小不能超过 50 MB')
  const totalSize = files.reduce((sum, item) => sum + item.file.size, 0)
  if (totalSize > MAX_TOTAL_SIZE) throw new Error('单次目录总大小不能超过 1 GB')
  return { name, files, totalSize }
}
