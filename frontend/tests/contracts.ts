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
    assert.equal(config.timeout, 0)
    return response(config, { status: 'partial' })
  }
  assert.equal(
    (await requestProjectFileParsing(id, [85, 86])).status,
    'partial',
  )
})
test('学习纠正携带读取版本，保留快照发布失败', async () => {
  http.defaults.adapter = async (config) => {
    assert.equal(config.method, 'patch')
    assert.equal(JSON.parse(config.data).version, 3)
    return response(config, {
      snapshot: { version: 4, published: false, error: '发布失败' },
    })
  }
  assert.equal(
    (
      await updateEntry(id, {
        version: 3,
        reason: '核对后纠正',
        content: '新内容',
      })
    ).snapshot.published,
    false,
  )
})
test('UTC 时间和登录返回地址符合实际契约', () => {
  assert.equal(
    serverDate('2026-09-08T07:18:22').toISOString(),
    '2026-09-08T07:18:22.000Z',
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
