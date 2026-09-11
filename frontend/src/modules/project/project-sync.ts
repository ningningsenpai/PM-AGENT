import {
  validateProjectFile,
  type PreparedProjectFile,
  type ProjectFileCandidate,
  type RejectedProjectFile,
} from '@/modules/project/file-upload'
import { hashProjectFile } from '@/modules/project/project-update'
import type {
  ProjectFileSyncManifestItem,
  ProjectFileSyncPlanRequest,
} from '@/modules/project/types'

export interface PreparedProjectFileSync {
  request: ProjectFileSyncPlanRequest
  filesByPath: Map<string, PreparedProjectFile>
  localRejections: RejectedProjectFile[]
}

/** 构建项目目录的完整同步清单，明显拒绝项仅上报元数据，不读取文件内容。 */
export async function prepareProjectFileSync(
  files: ProjectFileCandidate[],
): Promise<PreparedProjectFileSync> {
  const acceptedPaths = new Set<string>()
  const manifestPaths = new Set<string>()
  const items: ProjectFileSyncManifestItem[] = []
  const filesByPath = new Map<string, PreparedProjectFile>()
  const localRejections: RejectedProjectFile[] = []

  for (const input of files) {
    const validation = validateProjectFile(input, acceptedPaths)
    if (!validation.valid) {
      localRejections.push(validation.rejection)
      if (!manifestPaths.has(validation.rejection.relativePath)) {
        items.push(toManifestItem(input.file, validation.rejection.relativePath, null))
        manifestPaths.add(validation.rejection.relativePath)
      }
      continue
    }

    const contentHash = await hashProjectFile(input.file)
    items.push(toManifestItem(input.file, validation.candidate.relativePath, contentHash))
    manifestPaths.add(validation.candidate.relativePath)
    filesByPath.set(validation.candidate.relativePath, validation.candidate)
  }

  return {
    request: {
      snapshotComplete: true,
      scope: 'project',
      items,
    },
    filesByPath,
    localRejections,
  }
}

function toManifestItem(
  file: File,
  relativePath: string,
  contentHash: string | null,
): ProjectFileSyncManifestItem {
  return {
    relativePath,
    sizeBytes: file.size,
    sourceMtimeMs: file.lastModified,
    contentHash,
    contentType: file.type || null,
  }
}
