export function formatDate(value?: string | null) {
  if (!value) return '暂无记录'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '日期不可用' : date.toLocaleString('zh-CN', { hour12: false })
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '操作失败，请稍后重试'
}

export function safeRedirect(value: unknown) {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') && !value.includes('\\') && !/^\/(login|register)([/?#]|$)/.test(value)
    ? value : '/overview'
}
