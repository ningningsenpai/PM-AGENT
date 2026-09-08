export function serverDate(value: string) {
  // 项目、会话、报告及记忆的无时区时间使用 UTC。
  return new Date(
    /^\d{4}-\d{2}-\d{2}T/.test(value) && !/(Z|[+-]\d{2}:?\d{2})$/i.test(value)
      ? value + 'Z'
      : value,
  )
}

export function formatDate(value?: string | null) {
  if (!value) return '暂无记录'
  const date = serverDate(value)
  return Number.isNaN(date.getTime())
    ? '日期不可用'
    : date.toLocaleString('zh-CN', { hour12: false })
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '操作失败，请稍后重试'
}

export function formatLoginTime(value?: string | null) {
  if (!value) return '暂无记录'
  // 认证模块目前返回服务端本地时间，不将其误当成 UTC 二次转换。
  return value.replace('T', ' ').replace(/\.\d+$/, '')
}

export function safeRedirect(value: unknown) {
  return typeof value === 'string' &&
    value.startsWith('/') &&
    !value.startsWith('//') &&
    !value.includes('\\') &&
    !/^\/(login|register)([/?#]|$)/.test(value)
    ? value
    : '/overview'
}
