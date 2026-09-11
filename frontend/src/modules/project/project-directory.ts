import {
  isIgnoredProjectDirectory,
  type ProjectFileCandidate,
} from '@/modules/project/file-upload'

type ProjectDirectoryPermission = 'granted' | 'denied' | 'prompt'

interface ProjectDirectoryPermissionOptions {
  mode: 'read'
}

export interface ProjectFileHandle {
  kind: 'file'
  name: string
  getFile(): Promise<File>
}

export interface ProjectDirectoryHandle {
  kind: 'directory'
  name: string
  values(): AsyncIterableIterator<ProjectDirectoryHandle | ProjectFileHandle>
  queryPermission?(
    options: ProjectDirectoryPermissionOptions,
  ): Promise<ProjectDirectoryPermission>
  requestPermission?(
    options: ProjectDirectoryPermissionOptions,
  ): Promise<ProjectDirectoryPermission>
}

export interface ProjectDirectoryBinding {
  key: string
  userId: string
  projectId: string
  directoryName: string
  handle: ProjectDirectoryHandle
  boundAt: string
  lastSyncAt: string | null
}

export interface PendingProjectDirectorySelection {
  directoryName: string
  handle?: ProjectDirectoryHandle
  files?: ProjectFileCandidate[]
}

interface DirectoryPickerWindow extends Window {
  showDirectoryPicker?: (options?: {
    id?: string
    mode?: 'read'
    startIn?: ProjectDirectoryHandle
  }) => Promise<ProjectDirectoryHandle>
}

const databaseName = 'pm-agent-local'
const databaseVersion = 1
const bindingStoreName = 'project-directory-bindings'
const pendingSelections = new Map<string, PendingProjectDirectorySelection>()
let databasePromise: Promise<IDBDatabase> | null = null

export function projectDirectoryBindingKey(userId: string, projectId: string) {
  return `${userId}:${projectId}`
}

export function isProjectDirectoryPickerSupported() {
  return (
    typeof window !== 'undefined' &&
    typeof (window as DirectoryPickerWindow).showDirectoryPicker === 'function'
  )
}

export async function pickProjectDirectory(startIn?: ProjectDirectoryHandle) {
  const picker = (window as DirectoryPickerWindow).showDirectoryPicker
  if (!picker) throw new Error('当前浏览器不支持记住项目文件夹，请使用最新版 Chrome 或 Edge')
  return picker.call(window, {
    id: 'pm-agent-project-directory',
    mode: 'read',
    ...(startIn ? { startIn } : {}),
  })
}

export function isDirectoryPickerCancelled(error: unknown) {
  return error instanceof Error && error.name === 'AbortError'
}

export async function verifyProjectDirectoryPermission(
  handle: ProjectDirectoryHandle,
  requestPermission: boolean,
) {
  if (!handle.queryPermission) return true
  if ((await handle.queryPermission({ mode: 'read' })) === 'granted') return true
  if (!requestPermission || !handle.requestPermission) return false
  return (await handle.requestPermission({ mode: 'read' })) === 'granted'
}

/** 目录句柄不会提供可复用的 FileList，因此每次更新都从根目录重新构造相对路径。 */
export async function readProjectDirectory(
  handle: ProjectDirectoryHandle,
): Promise<ProjectFileCandidate[]> {
  const files: ProjectFileCandidate[] = []
  await readDirectory(handle, [], files)
  return files
}

async function readDirectory(
  handle: ProjectDirectoryHandle,
  parentSegments: string[],
  files: ProjectFileCandidate[],
) {
  for await (const entry of handle.values()) {
    if (entry.kind === 'directory') {
      if (isIgnoredProjectDirectory(entry.name)) continue
      await readDirectory(entry, [...parentSegments, entry.name], files)
      continue
    }
    const file = await entry.getFile()
    files.push({
      file,
      relativePath: [...parentSegments, entry.name].join('/'),
    })
  }
}

export async function saveProjectDirectoryBinding(
  userId: string,
  projectId: string,
  handle: ProjectDirectoryHandle,
) {
  const binding: ProjectDirectoryBinding = {
    key: projectDirectoryBindingKey(userId, projectId),
    userId,
    projectId,
    directoryName: handle.name,
    handle,
    boundAt: new Date().toISOString(),
    lastSyncAt: null,
  }
  await writeBinding(binding)
  return binding
}

export async function getProjectDirectoryBinding(userId: string, projectId: string) {
  return runRequest<ProjectDirectoryBinding | undefined>('readonly', (store) =>
    store.get(projectDirectoryBindingKey(userId, projectId)),
  )
}

export async function markProjectDirectorySynced(userId: string, projectId: string) {
  const binding = await getProjectDirectoryBinding(userId, projectId)
  if (!binding) return undefined
  const updated = { ...binding, lastSyncAt: new Date().toISOString() }
  await writeBinding(updated)
  return updated
}

export async function deleteProjectDirectoryBinding(userId: string, projectId: string) {
  await runRequest('readwrite', (store) =>
    store.delete(projectDirectoryBindingKey(userId, projectId)),
  )
}

export function rememberPendingProjectDirectory(
  projectId: string,
  selection: PendingProjectDirectorySelection,
) {
  pendingSelections.set(projectId, selection)
}

export function takePendingProjectDirectory(projectId: string) {
  const selection = pendingSelections.get(projectId)
  pendingSelections.delete(projectId)
  return selection
}

async function writeBinding(binding: ProjectDirectoryBinding) {
  await runRequest('readwrite', (store) => store.put(binding))
}

async function runRequest<T = undefined>(
  mode: IDBTransactionMode,
  createRequest: (store: IDBObjectStore) => IDBRequest<T>,
) {
  const database = await openDatabase()
  return new Promise<T>((resolve, reject) => {
    const transaction = database.transaction(bindingStoreName, mode)
    const request = createRequest(transaction.objectStore(bindingStoreName))
    let result: T
    request.onsuccess = () => {
      result = request.result
    }
    request.onerror = () => reject(request.error ?? new Error('本地项目文件夹操作失败'))
    transaction.oncomplete = () => resolve(result)
    transaction.onerror = () =>
      reject(transaction.error ?? new Error('本地项目文件夹事务执行失败'))
    transaction.onabort = () =>
      reject(transaction.error ?? new Error('本地项目文件夹操作已中止'))
  })
}

function openDatabase() {
  if (databasePromise) return databasePromise
  if (typeof indexedDB === 'undefined') {
    return Promise.reject(new Error('当前浏览器无法保存项目文件夹绑定'))
  }
  databasePromise = new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(databaseName, databaseVersion)
    request.onupgradeneeded = () => {
      const database = request.result
      if (!database.objectStoreNames.contains(bindingStoreName)) {
        database.createObjectStore(bindingStoreName, { keyPath: 'key' })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('本地项目文件夹数据库打开失败'))
  })
  return databasePromise
}
