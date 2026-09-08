import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'

const base = process.env.PM_TEST_API || 'http://127.0.0.1:18080'
assert.ok(
  ['127.0.0.1', 'localhost'].includes(new URL(base).hostname),
  '仅允许独立本地验收环境',
)
const email = process.env.PM_TEST_EMAIL
const password = process.env.PM_TEST_PASSWORD
const projectId = process.env.PM_TEST_PROJECT_ID
assert.ok(
  email && password && projectId,
  '请设置 PM_TEST_EMAIL、PM_TEST_PASSWORD 和 PM_TEST_PROJECT_ID',
)
let token = ''
async function call(method, path, data) {
  const response = await fetch(base + path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: 'Bearer ' + token } : {}),
    },
    body: data === undefined ? undefined : JSON.stringify(data),
  })
  return response.json()
}
const login = await call('POST', '/api/v1/auth/login', { email, password })
assert.equal(login.code, 200)
token = login.data.tokenValue
const prefix = '/api/v1/projects/' + projectId
const files = (await call('GET', prefix + '/files?businessCode=project')).data
const file = files.find((item) => item.relativePath === 'README.md')
assert.ok(file, '请先通过页面同步固定 README 样本')
assert.equal(file.analysisStatus, 'success')
const raw = await readFile(
  new URL('../tests/fixtures/project/README.md', import.meta.url),
)
const plan = await call('POST', prefix + '/files/sync/plan', {
  snapshotComplete: true,
  scope: 'project',
  items: [
    {
      relativePath: 'README.md',
      sizeBytes: raw.length,
      sourceMtimeMs: file.sourceMtimeMs,
      contentHash: createHash('sha256').update(raw).digest('hex'),
      contentType: 'text/markdown',
    },
  ],
})
assert.equal(plan.code, 200)
assert.equal(plan.data.unchanged.length, 1)
const conflict = await call('PATCH', prefix + '/files/' + file.id + '/path', {
  relativePath: file.relativePath,
  sourceMtimeMs: file.sourceMtimeMs,
  lockVersion: file.lockVersion + 100,
})
assert.equal(conflict.code, 30013)
const missing = await call('GET', '/api/v1/projects/90000000000000001')
assert.equal(missing.code, 30001)
const read = await call('GET', prefix + '/files/' + file.id + '/read-url')
assert.equal(read.code, 200)
assert.ok(['http:', 'https:'].includes(new URL(read.data.url).protocol))
const reports = (await call('GET', prefix + '/reports')).data
assert.ok(reports.length, '请先通过页面生成报告')
for (const report of reports) {
  const detail = await call('GET', prefix + '/reports/' + report.id)
  assert.equal(detail.data[0].markdown, report.markdown)
  assert.ok(report.evidence.length)
  const run = await call('GET', '/api/v1/agent/runs/' + report.runId)
  assert.equal(run.data.status, 'success')
}
const entries = (
  await call(
    'GET',
    '/api/v1/agent/context-entries?projectId=' + projectId + '&effective=false',
  )
).data
const entry = entries.find(
  (item) => item.content.includes('小林') && item.version >= 2,
)
assert.ok(entry, '请先通过页面学习并纠正验收负责人条目')
const bad = await call('PATCH', '/api/v1/agent/context-entries/' + entry.id, {
  version: entry.version - 1,
  reason: '验证过期版本保护',
  content: '不得保存此内容',
})
assert.equal(bad.code, 10003)
const invalid = await fetch(base + '/api/v1/projects', {
  headers: { Authorization: 'Bearer invalid-test-token' },
}).then((r) => r.json())
assert.equal(invalid.code, 20001)
console.log(
  JSON.stringify(
    {
      项目ID: projectId,
      重复目录同步: 'unchanged=1',
      文件版本冲突: conflict.code,
      无权限或不存在项目: missing.code,
      原文临时链接: '有效',
      报告详情恢复: reports.length + ' 份通过',
      学习版本冲突: bad.code,
      失效令牌: invalid.code,
    },
    null,
    2,
  ),
)
