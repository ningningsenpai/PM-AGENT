export function serverDate(value: string) {
  // 后端数据库时间使用 UTC，未携带时区的 ISO 时间按 UTC 解释。
  return new Date(/^\d{4}-\d{2}-\d{2}T/.test(value) && !/(Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value + 'Z' : value)
}

export function formatDate(value?: string | null) {
  if (!value) return '暂无记录'
  const date = serverDate(value)
  return Number.isNaN(date.getTime()) ? '日期不可用' : date.toLocaleString('zh-CN', { hour12: false })
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '操作失败，请稍后重试'
}

export function safeRedirect(value: unknown) {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') && !value.includes('\\') && !/^\/(login|register)([/?#]|$)/.test(value)
    ? value : '/overview'
}
