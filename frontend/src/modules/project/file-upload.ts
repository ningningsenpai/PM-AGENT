import { v4 as uuidv4 } from 'uuid'

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

export interface ProjectFileCandidate {
  file: File
  relativePath: string
}

export interface PreparedProjectFile {
  idempotencyKey: string
  relativePath: string
  sourceMtimeMs: number
  file: File
}

export interface RejectedProjectFile {
  relativePath: string
  reason: string
}

export type ProjectFileValidationResult =
  | { valid: true; candidate: PreparedProjectFile }
  | { valid: false; rejection: RejectedProjectFile }

export function projectFileCandidatesFromInput(files: File[]): ProjectFileCandidate[] {
  return files.map((file) => ({ file, relativePath: relativePathFromInput(file) }))
}

export function isIgnoredProjectDirectory(directoryName: string) {
  return ignoredDirectoryNames.has(directoryName.toLowerCase())
}

export function validateProjectFile(
  input: ProjectFileCandidate,
  acceptedPaths: Set<string>,
): ProjectFileValidationResult {
  const pathInfo = normalizeFilePath(input.relativePath)
  const rejectedReason = getRejectedReason(input.file, pathInfo.directorySegments)
  if (rejectedReason) {
    return {
      valid: false,
      rejection: { relativePath: pathInfo.relativePath, reason: rejectedReason },
    }
  }
  if (acceptedPaths.has(pathInfo.relativePath)) {
    return {
      valid: false,
      rejection: { relativePath: pathInfo.relativePath, reason: '相对路径重复' },
    }
  }

  acceptedPaths.add(pathInfo.relativePath)
  return {
    valid: true,
    candidate: {
      idempotencyKey: uuidv4(),
      relativePath: pathInfo.relativePath,
      sourceMtimeMs: input.file.lastModified,
      file: input.file,
    },
  }
}

function relativePathFromInput(file: File) {
  const rawPath = (file.webkitRelativePath || file.name).replaceAll('\\', '/').normalize('NFC')
  const segments = rawPath.split('/').filter(Boolean)
  const relativeSegments = file.webkitRelativePath && segments.length > 1 ? segments.slice(1) : segments

  return relativeSegments.join('/')
}

function normalizeFilePath(relativePath: string) {
  const segments = relativePath.replaceAll('\\', '/').normalize('NFC').split('/').filter(Boolean)

  return {
    relativePath: segments.join('/'),
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
