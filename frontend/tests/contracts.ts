import test, { beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { effectScope } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { http, request, RequestError, onUnauthorized } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import {
  getProjectDetail,
  requestProjectFileParsing,
} from '@/modules/project/api'
import { useOperation } from '@/modules/assistant/operation'
import { updateEntry } from '@/modules/assistant/api'
import { executeOperation } from '@/modules/assistant/api'
import { getReport } from '@/modules/report/api'
import { listTasks, createTask } from '@/modules/task/api'
import { renderMarkdown } from '@/shared/utils/markdown'
import { serverDate, safeRedirect } from '@/shared/utils/format'
import type { Run } from '@/modules/assistant/types'
import { useFileParsing } from '@/modules/project/file-parsing'
import type { ProjectFileResponse, ProjectFileParseResult } from '@/modules/project/types'
import { createConversation, renameConversation } from '@/modules/assistant/api'
import { mergePendingMessage, shouldSendOnEnter, useConversationMessages } from '@/modules/assistant/conversation-messages'
import type { ChatMessage } from '@/modules/assistant/types'
import {
  readProjectDirectory,
  rememberPendingProjectDirectory,
  takePendingProjectDirectory,
  verifyProjectDirectoryPermission,
  type ProjectDirectoryHandle,
  type ProjectFileHandle,
} from '@/modules/project/project-directory'
import {
  projectFileCandidatesFromInput,
  validateProjectFile,
} from '@/modules/project/file-upload'
class MemoryStorage {
  map = new Map<string, string>()
  getItem(key: string) {
    return this.map.get(key) ?? null
  }
  setItem(key: string, value: string) {
    this.map.set(key, String(value))
  }
  removeItem(key: string) {
    this.map.delete(key)
  }
  clear() {
    this.map.clear()
  }
}
Object.assign(globalThis, {
  localStorage: new MemoryStorage(),
  sessionStorage: new MemoryStorage(),
})
const id = '90707287462875137'
const conversation = '90707287462875239'
function run(status: Run['status'] = 'success'): Run {
  return {
    runId: '90707287462875341',
    projectId: id,
    conversationId: conversation,
    operation: 'chat',
    status,
    traceId: '测试追踪',
    result: {},
    error: status === 'failed' ? '模型处理失败' : null,
    events: [],
  }
}
function response(config: any, data: unknown, code = 200) {
  return {
    config,
    data: {
      code,
      message: code === 200 ? '成功' : '测试错误',
      data,
      traceId: '测试追踪',
    },
    status: 200,
    statusText: 'OK',
    headers: {},
  }
}

function localFile(name: string, relativePath = '') {
  const bytes = new TextEncoder().encode(`测试文件：${name}`)
  return {
    name,
    size: bytes.byteLength,
    type: 'text/plain',
    lastModified: 1760000000000,
    webkitRelativePath: relativePath,
    arrayBuffer: async () => bytes.buffer,
  } as File
}

function fileHandle(name: string): ProjectFileHandle {
  return {
    kind: 'file',
    name,
    getFile: async () => localFile(name),
  }
}

function directoryHandle(
  name: string,
  entries: Array<ProjectDirectoryHandle | ProjectFileHandle>,
): ProjectDirectoryHandle {
  return {
    kind: 'directory',
    name,
    async *values() {
      for (const entry of entries) yield entry
    },
  }
}
beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.token = 'test-token'
  localStorage.setItem('pm-agent-token', 'test-token')
  auth.user = {
    id: '90707287462875199',
    username: '验收',
    email: 'ui@example.test',
    status: 'enabled',
    lastLoginAt: null,
  }
  onUnauthorized(() => {})
})
test('实际成功码 200 和雪花 ID 字符串保持完整', async () => {
  http.defaults.adapter = async (config) => {
    assert.equal(config.url, `/api/v1/projects/${id}`)
    assert.equal(config.headers.get('Authorization'), 'Bearer test-token')
    assert.ok(config.headers.get('X-Trace-Id'))
    return response(config, { id })
  }
  assert.equal((await getProjectDetail(id)).id, id)
})
test('业务码 20001 使当前令牌失效，错误保留码和 traceId', async () => {
  let called = 0
  onUnauthorized(() => called++)
  http.defaults.adapter = async (config) => response(config, null, 20001)
  await assert.rejects(
    () => request({ url: '/失效登录' }),
    (error: unknown) =>
      error instanceof RequestError &&
      error.code === 20001 &&
      error.message.includes('测试追踪'),
  )
  assert.equal(called, 1)
})
test('旧令牌请求迟到的 401 业务响应不会注销新账号', async () => {
  let called = 0
  onUnauthorized(() => called++)
  http.defaults.adapter = async (config) => {
    localStorage.setItem('pm-agent-token', 'new-token')
    return response(config, null, 20001)
  }
  await assert.rejects(() => request({ url: '/旧请求' }))
  assert.equal(called, 0)
})
test('Markdown 拒绝原始 HTML、脚本链接和远程图片加载', () => {
  const html = renderMarkdown(
    '<script>alert(1)</script>\n<img src=x onerror=alert(1)>\n[跳转](javascript:alert(1))\n![图片](https://example.test/tracker.png)',
  )
  assert.doesNotMatch(html, /<script|<img|href="javascript:/i)
  assert.match(html, /&lt;script&gt;/)
  assert.match(
    renderMarkdown('[来源](https://example.test)'),
    /rel="noopener noreferrer"/,
  )
})
test('断网后刷新使用同一幂等键和相同内容恢复，运行失败不会当作成功', async () => {
  const scope = effectScope()
  const first = scope.run(() => useOperation(id, conversation))!
  const keys: string[] = []
  const payloads: string[] = []
  let calls = 0
  http.defaults.adapter = async (config) => {
    calls++
    keys.push(String(config.headers.get('X-Idempotency-Key')))
    payloads.push(config.data)
    if (calls === 1) throw new Error('断网')
    return response(config, run('failed'))
  }
  await first.start('chat', { content: '请核对文件' })
  assert.equal(first.unresolved.value, true)
  scope.stop()
  const recoveryScope = effectScope()
  const recovered = recoveryScope.run(() => useOperation(id, conversation))!
  await recovered.recover()
  assert.equal(keys[0], keys[1])
  assert.equal(payloads[0], payloads[1])
  assert.equal(recovered.run.value?.status, 'failed')
  assert.equal(recovered.unresolved.value, false)
  recoveryScope.stop()
})
test('重复点击只发起一次请求，明确完成后新操作使用新键', async () => {
  const scope = effectScope()
  const operation = scope.run(() => useOperation(id, conversation))!
  let finish: (value: any) => void = () => {}
  const keys: string[] = []
  http.defaults.adapter = (config) => {
    keys.push(String(config.headers.get('X-Idempotency-Key')))
    return new Promise((resolve) => {
      finish = (value) => resolve(response(config, value))
    })
  }
  const first = operation.start('chat', { content: '一次问答' })
  await new Promise((resolve) => setTimeout(resolve, 0))
  await operation.start('chat', { content: '重复点击' })
  assert.equal(keys.length, 1)
  finish(run('failed'))
  await first
  const retry = operation.start('chat', { content: '明确重试' })
  await new Promise((resolve) => setTimeout(resolve, 0))
  finish(run())
  await retry
  assert.notEqual(keys[0], keys[1])
  scope.stop()
})
test('已知运行只查询 GET，切换项目后不会写入旧页面或恢复记录', async () => {
  const scope = effectScope()
  const operation = scope.run(() => useOperation(id, conversation))!
  let resolveRequest: (value: any) => void = () => {}
  http.defaults.adapter = (config) =>
    new Promise((resolve) => {
      assert.equal(config.method, 'get')
      resolveRequest = (value) => resolve(response(config, value))
    })
  const pending = operation.track('90707287462875341')
  await new Promise((resolve) => setTimeout(resolve, 0))
  scope.stop()
  sessionStorage.clear()
  resolveRequest(run())
  await pending
  assert.equal(operation.run.value, null)
  assert.equal((sessionStorage as unknown as MemoryStorage).map.size, 0)
})
test('后台系统异常保留未确认操作，不建立新运行', async () => {
  const scope = effectScope()
  const operation = scope.run(() => useOperation(id, conversation))!
  http.defaults.adapter = async (config) => response(config, null, 90001)
  await operation.start('chat', { content: '测试' })
  assert.equal(operation.unresolved.value, true)
  scope.stop()
})
test('定向重试传递数字文件 ID、force 参数及独立解析超时', async () => {
  http.defaults.adapter = async (config) => {
    assert.equal(config.params.force, true)
    assert.deepEqual(JSON.parse(config.data), { fileIds: [85, 86] })
    assert.equal(config.headers.get('X-Idempotency-Key'), 'parse-once')
    assert.equal(config.timeout, 120000)
    return response(config, { status: 'partial' })
  }
  assert.equal(
    (await requestProjectFileParsing(id, [85, 86], 'parse-once')).status,
    'partial',
  )
})
test('学习纠正携带项目、读取版本及稳定幂等键，成功返回正式发布结果', async () => {
  http.defaults.adapter = async config => {
    assert.equal(config.method, 'patch')
    assert.equal(JSON.parse(config.data).projectId, id)
    assert.equal(JSON.parse(config.data).version, 3)
    assert.equal(config.headers.get('X-Idempotency-Key'), 'edit-once')
    return response(config, { publication: { version: 4, published: true, error: null } })
  }
  const result = await updateEntry(id, { projectId: id, version: 3, reason: '核对后纠正', content: '新内容' }, 'edit-once')
  assert.equal(result.publication.published, true)
})
test('旧无偏移时间按上海时区解释，登录返回地址符合实际契约', () => {
  assert.equal(
    serverDate('2026-09-08T07:18:22').toISOString(),
    '2026-09-07T23:18:22.000Z',
  )
  assert.equal(safeRedirect('//example.test'), '/overview')
  assert.equal(safeRedirect('/projects/' + id), '/projects/' + id)
})

test('开发和风险报告传递真实 kind，并从数组契约恢复详情', async () => {
  for (const kind of ['development', 'risk'] as const) {
    http.defaults.adapter = async (config) => {
      assert.equal(config.url, `/api/v1/projects/${id}/reports`)
      assert.equal(JSON.parse(config.data).kind, kind)
      assert.equal(config.headers.get('X-Idempotency-Key'), 'stable-report-key')
      return response(config, {
        ...run(),
        conversationId: null,
        operation: 'report',
      })
    }
    assert.equal(
      (await executeOperation(id, undefined, kind, {}, 'stable-report-key'))
        .status,
      'success',
    )
  }
  http.defaults.adapter = async (config) =>
    response(config, [{ id, projectId: id, markdown: '# 报告' }])
  assert.equal((await getReport(id, id)).markdown, '# 报告')
  http.defaults.adapter = async (config) => response(config, [])
  await assert.rejects(() => getReport(id, id), /报告不存在/)
})

test('真实模式的任务入口不会请求尚未开放的接口', async () => {
  let requests = 0
  http.defaults.adapter = async (config) => {
    requests++
    return response(config, [])
  }
  await assert.rejects(() => listTasks(id), /暂未开放/)
  await assert.rejects(
    () =>
      createTask({
        projectId: id,
        title: '测试',
        description: '',
        priority: 'p1',
      }),
    /暂未开放/,
  )
  assert.equal(requests, 0)
})

test('无法保存恢复信息时不发起有副作用的运行', async () => {
  const scope = effectScope()
  const operation = scope.run(() => useOperation(id, conversation))!
  const original = sessionStorage.setItem
  let requests = 0
  http.defaults.adapter = async (config) => {
    requests++
    return response(config, run())
  }
  sessionStorage.setItem = () => {
    throw new Error('存储不可用')
  }
  try {
    await operation.start('chat', { content: '不应提交' })
    assert.equal(requests, 0)
    assert.match(operation.error.value, /存储权限/)
  } finally {
    sessionStorage.setItem = original
    scope.stop()
  }
})

function parseFile(fileId: number, changes: Partial<ProjectFileResponse> = {}): ProjectFileResponse {
  return {
    id: fileId, projectId: id, businessCode: 'project', relativePath: `${fileId}.md`,
    fileName: `${fileId}.md`, storageName: `${fileId}.md`, minioPath: `project/${fileId}.md`,
    extension: 'md', contentType: 'text/plain', sizeBytes: 10, sourceMtimeMs: 1,
    quickFingerprint: '指纹', contentHash: `hash-${fileId}`, status: 'active', uploadStatus: 'success',
    analysisStatus: 'pending', detailRef: null, lastErrorCode: null, lastErrorMessage: null,
    lastFailedAt: null, parseAttempts: 0, lockVersion: 0, createdAt: '', updatedAt: '', ...changes,
  }
}
function parseResult(changes: Partial<ProjectFileParseResult> = {}): ProjectFileParseResult {
  return { status: 'success', candidateCount: 1, successCount: 1, failureCount: 0,
    failures: [], specificationStatus: 'updated', indexStatus: 'updated', ...changes }
}
const settleRequests = () => new Promise<void>((resolve) => setImmediate(resolve))

test('解析进度只统计本轮候选，文件完成后保持锁定直至上下文发布结束', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const scope = effectScope()
  let snapshot = [parseFile(1), parseFile(2, { parseAttempts: 1, analysisStatus: 'failed' }),
    parseFile(3, { parseAttempts: 1, detailRef: '旧详情', analysisStatus: 'success' }),
    parseFile(4, { parseAttempts: 3 }), parseFile(5, { status: 'upload_failed' })]
  let finish: (result: ProjectFileParseResult) => void = () => {}
  let posts = 0
  let gets = 0
  http.defaults.adapter = async config => {
    if (config.method === 'get') { gets++; return response(config, snapshot) }
    posts++
    return new Promise(resolve => { finish = value => resolve(response(config, value)) })
  }
  const parsing = scope.run(() => useFileParsing(id, () => {}))!
  try {
    const first = parsing.start()
    await parsing.start()
    assert.equal(parsing.busy.value, true)
    await settleRequests()
    assert.equal(posts, 1)
    assert.equal(parsing.total.value, 2)
    assert.equal(parsing.percentage.value, 0)
    snapshot = snapshot.map(file => file.id === 1 ? { ...file, parseAttempts: 1 } : file)
    t.mock.timers.tick(1500)
    await settleRequests()
    assert.equal(parsing.percentage.value, 50)
    snapshot = snapshot.map(file => file.id === 2 ? { ...file, parseAttempts: 2 } : file)
    t.mock.timers.tick(1500)
    await settleRequests()
    assert.equal(parsing.percentage.value, 100)
    assert.equal(parsing.phase.value, 'publishing')
    assert.equal(parsing.busy.value, true)
    await parsing.start()
    assert.equal(posts, 1)
    finish(parseResult({ candidateCount: 2, failureCount: 1, status: 'partial' }))
    await first
    assert.equal(parsing.phase.value, 'error')
    assert.equal(parsing.result.value?.status, 'partial')
    assert.equal(parsing.busy.value, false)
    const finishedGets = gets
    t.mock.timers.tick(5000)
    await settleRequests()
    assert.equal(gets, finishedGets)
  } finally { scope.stop() }
})

test('定向重试不会把历史成功计入本轮，进度读取失败不重复触发解析', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const scope = effectScope()
  let snapshot = [parseFile(1, { parseAttempts: 4, detailRef: '旧详情', analysisStatus: 'success' }), parseFile(2)]
  let failPoll = false
  let finish: () => void = () => {}
  let posts = 0
  http.defaults.adapter = async config => {
    if (config.method === 'get') {
      if (failPoll) throw new Error('进度读取断网')
      return response(config, snapshot)
    }
    posts++
    assert.deepEqual(JSON.parse(config.data), { fileIds: [1] })
    return new Promise(resolve => { finish = () => resolve(response(config, parseResult())) })
  }
  const parsing = scope.run(() => useFileParsing(id, () => {}))!
  try {
    const pending = parsing.start([1])
    await settleRequests()
    assert.equal(parsing.total.value, 1)
    assert.equal(parsing.percentage.value, 0)
    failPoll = true
    t.mock.timers.tick(1500)
    await settleRequests()
    assert.match(parsing.progressError.value, /进度暂时无法更新/)
    assert.equal(parsing.busy.value, true)
    await parsing.start([1])
    assert.equal(posts, 1)
    failPoll = false
    snapshot = [parseFile(1, { parseAttempts: 5, detailRef: '新详情', analysisStatus: 'success' })]
    t.mock.timers.tick(1500)
    await settleRequests()
    assert.equal(parsing.percentage.value, 100)
    assert.equal(parsing.progressError.value, '')
    finish()
    await pending
  } finally { scope.stop() }
})

test('解析完成后丢弃迟到进度，弹窗本轮结束后不能再次提交', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const scope = effectScope()
  let reads = 0
  let posts = 0
  let finish: () => void = () => {}
  let latePoll: () => void = () => {}
  let fileUpdates = 0
  http.defaults.adapter = async config => {
    if (config.method === 'get') {
      if (++reads === 1) return response(config, [parseFile(1)])
      return new Promise(resolve => { latePoll = () => resolve(response(config, [parseFile(1)])) })
    }
    posts++
    return new Promise(resolve => { finish = () => resolve(response(config, parseResult())) })
  }
  const parsing = scope.run(() => useFileParsing(id, () => fileUpdates++))!
  try {
    const pending = parsing.start()
    await settleRequests()
    t.mock.timers.tick(1500)
    await settleRequests()
    finish()
    await pending
    latePoll()
    await settleRequests()
    assert.equal(parsing.percentage.value, 100)
    assert.equal(parsing.phase.value, 'finished')
    assert.equal(fileUpdates, 1)
    await parsing.start()
    assert.equal(posts, 1)
  } finally { scope.stop() }
})

test('无候选文件仍等待上下文更新，确认失败后解除锁定且不自动重跑模型', async () => {
  const scope = effectScope()
  let rejectParse: (error: Error) => void = () => {}
  let parsePosts = 0
  http.defaults.adapter = async config => {
    if (config.method === 'get') return response(config, [])
    if (config.url?.endsWith('/parse/recover')) {
      return response(config, { runId: 'failed-run', status: 'failed', retryable: true, retryMode: 'new_key', leaseUntil: null, serverTime: '2026-09-10T14:00:00+08:00', result: null, error: '解析失败' })
    }
    parsePosts++
    return new Promise((_resolve, reject) => { rejectParse = reject })
  }
  const parsing = scope.run(() => useFileParsing(id, () => {}))!
  try {
    const pending = parsing.start()
    await settleRequests()
    assert.equal(parsing.total.value, 0)
    assert.equal(parsing.percentage.value, 0)
    assert.equal(parsing.phase.value, 'publishing')
    rejectParse(new Error('请求中断'))
    await pending
    assert.equal(parsing.phase.value, 'error')
    assert.equal(parsing.percentage.value, 0)
    assert.equal(parsing.result.value, null)
    assert.match(parsing.error.value, /立即重试/)
    assert.equal(parsing.hasPending.value, false)
    await parsing.start()
    assert.equal(parsePosts, 1)
  } finally { scope.stop() }
})
test('已绑定目录重新扫描时构造相对路径并跳过依赖目录', async () => {
  const root = directoryHandle('PM-AGENT', [
    fileHandle('README.md'),
    directoryHandle('src', [fileHandle('main.ts')]),
    directoryHandle('node_modules', [fileHandle('ignored.js')]),
  ])

  const files = await readProjectDirectory(root)
  assert.deepEqual(
    files.map((file) => file.relativePath),
    ['README.md', 'src/main.ts'],
  )
  assert.equal(validateProjectFile(files[1], new Set()).valid, true)
})
test('目录权限失效时只在用户触发更新后请求恢复', async () => {
  let requested = 0
  const handle = directoryHandle('PM-AGENT', [])
  handle.queryPermission = async () => 'prompt'
  handle.requestPermission = async () => {
    requested++
    return 'granted'
  }

  assert.equal(await verifyProjectDirectoryPermission(handle, false), false)
  assert.equal(requested, 0)
  assert.equal(await verifyProjectDirectoryPermission(handle, true), true)
  assert.equal(requested, 1)
})
test('创建项目的临时目录选择只会被详情页消费一次', () => {
  const files = projectFileCandidatesFromInput([
    localFile('README.md', 'PM-AGENT/README.md'),
  ])
  rememberPendingProjectDirectory(id, { directoryName: 'PM-AGENT', files })
  assert.equal(takePendingProjectDirectory(id)?.files?.[0].relativePath, 'README.md')
  assert.equal(takePendingProjectDirectory(id), undefined)
})

test('解析结果不确定且后端无记录时以原幂等键补发一次，成功后清除恢复记录', async () => {
  const scope = effectScope()
  const keys: string[] = []
  let attempts = 0
  http.defaults.adapter = async config => {
    if (config.method === 'get') return response(config, [])
    if (config.url?.endsWith('/parse/recover')) {
      assert.equal(config.headers.get('X-Idempotency-Key'), keys[0])
      return response(config, { runId: null, status: 'absent', retryable: true, retryMode: 'same_key', leaseUntil: null, serverTime: '2026-09-10T14:00:00+08:00', result: null, error: null })
    }
    keys.push(config.headers.get('X-Idempotency-Key') as string)
    if (++attempts === 1) throw new Error('连接中断')
    return response(config, parseResult({ candidateCount: 0, successCount: 0 }))
  }
  const parsing = scope.run(() => useFileParsing(id, () => {}))!
  try {
    await parsing.start()
    assert.equal(keys.length, 2)
    assert.equal(keys[0], keys[1])
    assert.equal(parsing.phase.value, 'finished')
    assert.equal(parsing.hasPending.value, false)
    assert.equal((sessionStorage as unknown as MemoryStorage).map.size, 0)
  } finally { scope.stop() }
})

test('解析请求超时后按服务端租约轮询，失败后解锁并使用新键重试', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const scope = effectScope()
  let recoveries = 0
  const keys: string[] = []
  http.defaults.adapter = async config => {
    if (config.method === 'get') return response(config, [])
    if (config.url?.endsWith('/parse/recover')) {
      recoveries++
      if (recoveries === 1) {
        return response(config, {
          runId: 'running-run', status: 'running', retryable: false, retryMode: null,
          serverTime: '2026-09-10T10:00:00+08:00', leaseUntil: '2026-09-10T10:00:10+08:00',
          result: null, error: null,
        })
      }
      return response(config, {
        runId: 'failed-run', status: 'failed', retryable: true, retryMode: 'new_key',
        serverTime: '2026-09-10T10:00:05+08:00', leaseUntil: null,
        result: null, error: '运行租约已过期',
      })
    }
    keys.push(config.headers.get('X-Idempotency-Key') as string)
    if (keys.length === 1) throw Object.assign(new Error('请求超时'), { code: 'ECONNABORTED' })
    return response(config, parseResult({ candidateCount: 0, successCount: 0 }))
  }
  const parsing = scope.run(() => useFileParsing(id, () => {}))!
  try {
    const pending = parsing.start()
    await settleRequests()
    assert.equal(parsing.busy.value, false)
    assert.equal(parsing.recovering.value, true)
    assert.equal(parsing.leaseUntil.value, '2026-09-10T10:00:10+08:00')
    t.mock.timers.tick(4999)
    await settleRequests()
    assert.equal(recoveries, 1)
    t.mock.timers.tick(1)
    await pending
    assert.equal(recoveries, 2)
    assert.equal(parsing.recovering.value, false)
    assert.equal(parsing.hasPending.value, false)
    assert.match(parsing.error.value, /立即重试/)

    assert.equal(parsing.reset(), true)
    await parsing.start()
    assert.equal(keys.length, 2)
    assert.notEqual(keys[0], keys[1])
  } finally { scope.stop() }
})

test('连续两次无效 running 租约会停止轮询并保留原幂等键', async () => {
  const scope = effectScope()
  let recoveries = 0
  http.defaults.adapter = async config => {
    if (config.method === 'get') return response(config, [])
    if (config.url?.endsWith('/parse/recover')) {
      recoveries++
      return response(config, {
        runId: 'broken-run', status: 'running', retryable: false, retryMode: null,
        serverTime: '2026-09-10T10:00:01+08:00', leaseUntil: '2026-09-10T10:00:00+08:00',
        result: null, error: null,
      })
    }
    throw new Error('连接中断')
  }
  const parsing = scope.run(() => useFileParsing(id, () => {}))!
  try {
    await parsing.start()
    assert.equal(recoveries, 2)
    assert.equal(parsing.recovering.value, false)
    assert.equal(parsing.busy.value, false)
    assert.equal(parsing.hasPending.value, true)
    assert.match(parsing.error.value, /已停止自动查询/)
  } finally { scope.stop() }
})

test('页面重新进入时自动恢复未确认请求，恢复接口断网不锁定页面', async () => {
  const userId = useAuthStore().user!.id
  sessionStorage.setItem(`pm-file-parse:${userId}:${id}`, JSON.stringify({
    key: 'stored-key', fileIds: [7], startedAt: '2026-09-10T09:59:00+08:00',
  }))
  let recoveries = 0
  http.defaults.adapter = async config => {
    assert.ok(config.url?.endsWith('/parse/recover'))
    recoveries++
    throw new Error('恢复网络不可用')
  }
  const scope = effectScope()
  const parsing = scope.run(() => useFileParsing(id, () => {}))!
  try {
    await settleRequests()
    assert.equal(recoveries, 1)
    assert.equal(parsing.busy.value, false)
    assert.equal(parsing.recovering.value, false)
    assert.equal(parsing.hasPending.value, true)
    assert.deepEqual(parsing.pendingFileIds.value, [7])
    assert.match(parsing.error.value, /恢复信息已保留/)
  } finally { scope.stop() }
})

test('刷新列表可单次确认待恢复运行，running 状态不启动持续轮询', async () => {
  const userId = useAuthStore().user!.id
  sessionStorage.setItem(`pm-file-parse:${userId}:${id}`, JSON.stringify({
    key: 'refresh-recover-key', fileIds: null, startedAt: '2026-09-10T10:00:00+08:00',
  }))
  let recoveries = 0
  http.defaults.adapter = async config => {
    assert.ok(config.url?.endsWith('/parse/recover'))
    recoveries++
    return response(config, {
      runId: 'refresh-running', status: 'running', retryable: false, retryMode: null,
      serverTime: '2026-09-10T10:00:00+08:00', leaseUntil: '2026-09-10T10:02:00+08:00',
      result: null, error: null,
    })
  }
  const scope = effectScope()
  const parsing = scope.run(() => useFileParsing(id, () => {}))!
  try {
    await parsing.recoverOnce()
    await settleRequests()
    assert.equal(recoveries, 1)
    assert.equal(parsing.recovering.value, false)
    assert.equal(parsing.hasPending.value, true)
    assert.equal(parsing.phase.value, 'parsing')
  } finally { scope.stop() }
})

test('离开解析组件后停止读取并忽略迟到结果', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const scope = effectScope()
  let finish: () => void = () => {}
  let gets = 0
  http.defaults.adapter = async config => {
    if (config.method === 'get') { gets++; return response(config, [parseFile(1)]) }
    return new Promise(resolve => { finish = () => resolve(response(config, parseResult())) })
  }
  const parsing = scope.run(() => useFileParsing(id, () => {}))!
  const pending = parsing.start()
  await settleRequests()
  scope.stop()
  finish()
  await pending
  t.mock.timers.tick(5000)
  await settleRequests()
  assert.equal(gets, 1)
  assert.equal(parsing.result.value, null)
})

test('新建会话由后端命名，修改名称使用持久化接口', async () => {
  http.defaults.adapter = async config => {
    assert.deepEqual(JSON.parse(config.data), { projectId: id })
    return response(config, { id: conversation, projectId: id, title: '项目对话-1' })
  }
  assert.equal((await createConversation(id)).title, '项目对话-1')
  http.defaults.adapter = async config => {
    assert.equal(config.method, 'patch')
    assert.equal(config.url, `/api/v1/agent/conversations/${conversation}`)
    assert.deepEqual(JSON.parse(config.data), { title: '需求讨论' })
    return response(config, { id: conversation, projectId: id, title: '需求讨论' })
  }
  assert.equal((await renameConversation(conversation, '需求讨论')).title, '需求讨论')
})

test('Enter 发送，Shift Enter 换行，中文输入法确认和长按不发送', () => {
  const enter = { key: 'Enter', shiftKey: false, isComposing: false, keyCode: 13, repeat: false }
  assert.equal(shouldSendOnEnter(enter), true)
  for (const changes of [{ shiftKey: true }, { isComposing: true }, { keyCode: 229 }, { repeat: true }, { key: 'a' }]) {
    assert.equal(shouldSendOnEnter({ ...enter, ...changes }), false)
  }
})

test('用户消息立即显示，重复发送被阻止，服务器历史按请求标识替换临时消息', async () => {
  const scope = effectScope()
  let finish: () => void = () => {}
  let posts = 0
  let history: ChatMessage[] = []
  http.defaults.adapter = async config => {
    if (config.method === 'get') return response(config, history)
    posts++
    const key = String(config.headers.get('X-Idempotency-Key'))
    return new Promise(resolve => { finish = () => {
      history = [{ id: '1', role: 'user', content: '立即显示的问题', runId: run().runId, requestKey: key, createdAt: '' },
        { id: '2', role: 'assistant', content: '回答', runId: run().runId, requestKey: key, createdAt: '' }]
      resolve(response(config, { ...run(), result: { userMessageId: '1' } }))
    } })
  }
  const chat = scope.run(() => useConversationMessages(id, conversation, () => {}))!
  try {
    const pending = chat.send('立即显示的问题')
    assert.equal(chat.visibleMessages.value.length, 1)
    assert.equal(chat.visibleMessages.value[0].content, '立即显示的问题')
    await chat.send('重复发送')
    await settleRequests()
    assert.equal(posts, 1)
    finish()
    await pending
    await settleRequests()
    assert.deepEqual(chat.visibleMessages.value.map(item => item.id), ['1', '2'])
  } finally { scope.stop() }
})

test('相同正文的两次提问不会误去重，恢复中的请求与服务器记录正确合并', async () => {
  const first: ChatMessage = { id: '1', role: 'user', content: '同一问题', runId: 'first-run', createdAt: '', requestKey: 'first-key' }
  const second: ChatMessage = { ...first, id: 'pending:second-key', runId: '', requestKey: 'second-key' }
  assert.equal(mergePendingMessage([first], second, null).length, 2)
  sessionStorage.setItem(`pm-operation:${useAuthStore().user?.id}:${id}:${conversation}`, JSON.stringify({
    key: 'second-key', kind: 'chat', payload: { content: '同一问题' }, terminal: false, startedAt: '2026-09-08T00:00:00Z',
  }))
  http.defaults.adapter = async config => response(config, [first, { ...second, id: '2', runId: 'second-run' }])
  const scope = effectScope()
  const chat = scope.run(() => useConversationMessages(id, conversation, () => {}))!
  await chat.load()
  assert.deepEqual(chat.visibleMessages.value.map(item => item.id), ['1', '2'])
  assert.equal(chat.operation.unresolved.value, true)
  scope.stop()
})


test('草稿确认绑定精确版本和所选字符串 ID，部分发布不会变成成功', async () => {
  const { confirmDraft } = await import('@/modules/assistant/api')
  http.defaults.adapter = async config => {
    assert.equal(config.url, `/api/v1/agent/learning-drafts/${id}/confirm`)
    assert.equal(config.params.projectId, id)
    assert.deepEqual(JSON.parse(config.data), { version: 4, candidateIds: [conversation] })
    return response(config, { id, state: 'partial', publications: { project: { published: false, error: '存储不可用' } } })
  }
  assert.equal((await confirmDraft(id, id, 4, [conversation])).state, 'partial')
})

test('定向反馈使用独立接口，断网恢复保持候选范围、版本和幂等键', async () => {
  let firstKey: unknown
  let calls = 0
  const scope = effectScope()
  const operation = scope.run(() => useOperation(id, conversation))!
  const payload = { draftId: id, version: 2, candidateIds: [conversation], feedback: '请区分适用场景' }
  http.defaults.adapter = async config => {
    assert.equal(config.url, `/api/v1/agent/learning-drafts/${id}/refine`)
    const { draftId: _id, ...expected } = payload
    assert.deepEqual(JSON.parse(config.data), expected)
    assert.equal(config.params.projectId, id)
    if (++calls === 1) { firstKey = config.headers.get('X-Idempotency-Key'); throw new Error('模拟断网') }
    assert.equal(config.headers.get('X-Idempotency-Key'), firstKey)
    return response(config, { ...run(), operation: 'learn_refine', result: { draftId: id, draftVersion: 4 } })
  }
  await operation.start('learn_refine', payload)
  assert.equal(operation.unresolved.value, true)
  await operation.recover()
  assert.equal(operation.unresolved.value, false)
  assert.equal(operation.run.value?.result.draftVersion, 4)
  scope.stop()
})


test('定向反馈后保留未选中条目，仅勾选新整理的候选', async () => {
  const { reconcileSelection } = await import('@/modules/assistant/learning')
  assert.deepEqual(reconcileSelection(['habit', 'rule'], ['rule', 'habit-a', 'habit-b'], ['habit']), ['habit-a', 'habit-b'])
  assert.deepEqual(reconcileSelection(['rule'], ['rule'], []), [])
})
