import { v4 as uuidv4 } from 'uuid'
import type {
  ProjectFileUploadBatch,
  ProjectFileUploadFileInfo,
  ProjectFileUploadManifest,
} from '@/modules/project/types'

export const PROJECT_FILE_BATCH_SIZE = 50
export const PROJECT_FILE_BATCH_MAX_BYTES = 240 * 1024 * 1024
export const PROJECT_FILE_MAX_ATTEMPTS = 3

const maxFileSizeBytes = 50 * 1024 * 1024

const ignoredDirectoryNames = new Set([
  '.git',
  '.gradle',
  '.idea',
  '.mvn',
  '.mypy_cache',
  '.pytest_cache',
  '.qdrant-data',
  '.svn',
  '.venv',
  '.vscode',
  '__pycache__',
  'build',
  'coverage',
  'dist',
  'module',
  'mysql-data',
  'node_modules',
  'out',
  'target',
  'test',
  'tests',
  'venv',
])

const ignoredFileNames = new Set(['.ds_store', 'desktop.ini', 'thumbs.db'])

const blockedExtensions = new Set([
  '7z',
  'a',
  'apk',
  'appimage',
  'avi',
  'bin',
  'bmp',
  'bz2',
  'class',
  'dll',
  'dmg',
  'dylib',
  'ear',
  'exe',
  'flac',
  'gif',
  'gz',
  'ico',
  'iso',
  'jar',
  'jpeg',
  'jpg',
  'key',
  'lib',
  'map',
  'mkv',
  'mov',
  'mp3',
  'mp4',
  'msi',
  'o',
  'obj',
  'ogg',
  'pem',
  'png',
  'pyc',
  'pyo',
  'rar',
  'so',
  'tar',
  'tiff',
  'war',
  'wav',
  'webm',
  'webp',
  'xz',
  'zip',
])

const blockedMimePrefixes = ['audio/', 'image/', 'video/']
const blockedMimeTypes = new Set([
  'application/java-archive',
  'application/vnd.android.package-archive',
  'application/x-7z-compressed',
  'application/x-apple-diskimage',
  'application/x-dosexec',
  'application/x-executable',
  'application/x-msdownload',
  'application/x-rar-compressed',
  'application/x-tar',
  'application/zip',
])

export interface PreparedProjectFile extends ProjectFileUploadFileInfo {
  file: File
}

export interface RejectedProjectFile {
  relativePath: string
  reason: string
}

export interface ProjectFileFilterResult {
  acceptedFiles: PreparedProjectFile[]
  rejectedFiles: RejectedProjectFile[]
}

export interface ProjectFileUploadRoundBatch {
  batch: ProjectFileUploadBatch
  files: File[]
  candidates: PreparedProjectFile[]
}

export interface ProjectFileUploadRound {
  manifest: ProjectFileUploadManifest
  batches: ProjectFileUploadRoundBatch[]
}

export function prepareProjectFiles(files: File[]): ProjectFileFilterResult {
  const acceptedFiles: PreparedProjectFile[] = []
  const rejectedFiles: RejectedProjectFile[] = []
  const acceptedPaths = new Set<string>()

  for (const file of files) {
    const pathInfo = normalizeFilePath(file)
    const rejectedReason = getRejectedReason(file, pathInfo.directorySegments)

    if (rejectedReason) {
      rejectedFiles.push({ relativePath: pathInfo.relativePath, reason: rejectedReason })
      continue
    }

    if (acceptedPaths.has(pathInfo.relativePath)) {
      rejectedFiles.push({ relativePath: pathInfo.relativePath, reason: '相对路径重复' })
      continue
    }

    acceptedPaths.add(pathInfo.relativePath)
    acceptedFiles.push({
      clientFileId: uuidv4(),
      businessCode: 'project',
      relativePath: pathInfo.relativePath,
      fileName: file.name.normalize('NFC'),
      sizeBytes: file.size,
      sourceMtimeMs: file.lastModified,
      file,
    })
  }

  return { acceptedFiles, rejectedFiles }
}

export function createProjectFileUploadRound(options: {
  userId: number
  projectId: number
  requestId: string
  attemptNo: number
  originalTotalFiles: number
  files: PreparedProjectFile[]
}): ProjectFileUploadRound {
  const roundBatches: ProjectFileUploadRoundBatch[] = []
  const candidateGroups = splitUploadCandidates(options.files)

  for (const candidates of candidateGroups) {
    const batchId = uuidv4()
    const idempotencyKey = uuidv4()
    const fileInfos = candidates.map(toFileInfo)
    const batch: ProjectFileUploadBatch = {
      userId: options.userId,
      projectId: options.projectId,
      requestId: options.requestId,
      attemptNo: options.attemptNo,
      batchId,
      idempotencyKey,
      fileCount: candidates.length,
      files: fileInfos,
    }

    roundBatches.push({
      batch,
      files: candidates.map((candidate) => candidate.file),
      candidates,
    })
  }

  const manifest: ProjectFileUploadManifest = {
    userId: options.userId,
    projectId: options.projectId,
    requestId: options.requestId,
    executionStatus: options.attemptNo === 1 ? 'initial' : 'retry',
    attemptNo: options.attemptNo,
    originalTotalFiles: options.originalTotalFiles,
    roundTotalFiles: options.files.length,
    totalBatchCount: roundBatches.length,
    batches: roundBatches.map(({ batch }) => ({
      batchId: batch.batchId,
      fileCount: batch.fileCount,
    })),
  }

  return { manifest, batches: roundBatches }
}

function splitUploadCandidates(files: PreparedProjectFile[]) {
  const groups: PreparedProjectFile[][] = []
  let currentGroup: PreparedProjectFile[] = []
  let currentSizeBytes = 0

  for (const file of files) {
    const exceedsCount = currentGroup.length >= PROJECT_FILE_BATCH_SIZE
    const exceedsSize =
      currentGroup.length > 0 && currentSizeBytes + file.sizeBytes > PROJECT_FILE_BATCH_MAX_BYTES

    if (exceedsCount || exceedsSize) {
      groups.push(currentGroup)
      currentGroup = []
      currentSizeBytes = 0
    }

    currentGroup.push(file)
    currentSizeBytes += file.sizeBytes
  }

  if (currentGroup.length) {
    groups.push(currentGroup)
  }

  return groups
}

function normalizeFilePath(file: File) {
  const rawPath = (file.webkitRelativePath || file.name).replaceAll('\\', '/').normalize('NFC')
  const segments = rawPath.split('/').filter(Boolean)
  const relativeSegments = file.webkitRelativePath && segments.length > 1 ? segments.slice(1) : segments

  return {
    relativePath: relativeSegments.join('/'),
    directorySegments: segments.slice(0, -1).map((segment) => segment.toLowerCase()),
  }
}

function getRejectedReason(file: File, directorySegments: string[]) {
  const ignoredDirectory = directorySegments.find((segment) => ignoredDirectoryNames.has(segment))
  if (ignoredDirectory) return `命中忽略目录：${ignoredDirectory}`

  const normalizedFileName = file.name.toLowerCase()
  if (normalizedFileName === '.env' || normalizedFileName.startsWith('.env.')) {
    return '本地环境变量文件'
  }
  if (ignoredFileNames.has(normalizedFileName)) return '系统或 IDE 临时文件'
  if (file.size === 0) return '空文件'
  if (file.size > maxFileSizeBytes) return '单文件超过 50MB'

  const extension = getExtension(normalizedFileName)
  if (blockedExtensions.has(extension)) return `不支持的文件后缀：.${extension}`

  const mimeType = file.type.toLowerCase()
  if (
    blockedMimeTypes.has(mimeType) ||
    blockedMimePrefixes.some((prefix) => mimeType.startsWith(prefix))
  ) {
    return `不支持的文件类型：${mimeType}`
  }

  return ''
}

function getExtension(fileName: string) {
  const dotIndex = fileName.lastIndexOf('.')
  return dotIndex > 0 && dotIndex < fileName.length - 1 ? fileName.slice(dotIndex + 1) : ''
}

function toFileInfo(file: PreparedProjectFile): ProjectFileUploadFileInfo {
  return {
    clientFileId: file.clientFileId,
    businessCode: file.businessCode,
    relativePath: file.relativePath,
    fileName: file.fileName,
    sizeBytes: file.sizeBytes,
    sourceMtimeMs: file.sourceMtimeMs,
  }
}
