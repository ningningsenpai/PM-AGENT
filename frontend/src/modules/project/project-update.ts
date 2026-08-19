import type { PreparedProjectFile } from '@/modules/project/file-upload'
import type { ProjectFileResponse } from '@/modules/project/types'

export interface HashedProjectFile extends PreparedProjectFile {
  contentHash: string
}

export interface MatchedProjectFile {
  local: HashedProjectFile
  remote: ProjectFileResponse
}

export interface ProjectFileDiff {
  unchanged: MatchedProjectFile[]
  added: HashedProjectFile[]
  modified: MatchedProjectFile[]
  moved: MatchedProjectFile[]
  deleted: ProjectFileResponse[]
}

export async function buildProjectFileDiff(
  localFiles: PreparedProjectFile[],
  remoteFiles: ProjectFileResponse[],
  observedLocalPaths = new Set(localFiles.map((file) => file.relativePath)),
): Promise<ProjectFileDiff> {
  const hashedFiles: HashedProjectFile[] = []
  for (const local of localFiles) {
    hashedFiles.push({ ...local, contentHash: await hashProjectFile(local.file) })
  }

  const unchanged: MatchedProjectFile[] = []
  const modified: MatchedProjectFile[] = []
  const moved: MatchedProjectFile[] = []
  const added: HashedProjectFile[] = []
  const matchedRemoteIds = new Set<number>()
  const remoteByPath = new Map(remoteFiles.map((file) => [file.relativePath, file]))
  const unmatchedLocal: HashedProjectFile[] = []

  for (const local of hashedFiles) {
    const remote = remoteByPath.get(local.relativePath)
    if (!remote) {
      unmatchedLocal.push(local)
      continue
    }
    matchedRemoteIds.add(remote.id)
    const match = { local, remote }
    if (isUnchanged(local, remote)) unchanged.push(match)
    else modified.push(match)
  }

  const movableByHash = new Map<string, ProjectFileResponse[]>()
  for (const remote of remoteFiles) {
    if (
      matchedRemoteIds.has(remote.id) ||
      remote.status !== 'active' ||
      remote.uploadStatus !== 'success'
    ) {
      continue
    }
    const candidates = movableByHash.get(remote.contentHash) ?? []
    candidates.push(remote)
    movableByHash.set(remote.contentHash, candidates)
  }

  const localByHash = new Map<string, HashedProjectFile[]>()
  for (const local of unmatchedLocal) {
    const candidates = localByHash.get(local.contentHash) ?? []
    candidates.push(local)
    localByHash.set(local.contentHash, candidates)
  }

  for (const [contentHash, localCandidates] of localByHash) {
    const remoteCandidates = movableByHash.get(contentHash) ?? []
    if (localCandidates.length === 1 && remoteCandidates.length === 1) {
      const local = localCandidates[0]
      const remote = remoteCandidates[0]
      matchedRemoteIds.add(remote.id)
      moved.push({ local, remote })
      continue
    }
    added.push(...localCandidates)
  }

  return {
    unchanged,
    added,
    modified,
    moved,
    deleted: remoteFiles.filter(
      (file) =>
        !matchedRemoteIds.has(file.id) &&
        !observedLocalPaths.has(file.relativePath),
    ),
  }
}

export async function hashProjectFile(file: File): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer())
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

function isUnchanged(local: HashedProjectFile, remote: ProjectFileResponse) {
  return (
    remote.status === 'active' &&
    remote.uploadStatus === 'success' &&
    remote.contentHash === local.contentHash
  )
}
