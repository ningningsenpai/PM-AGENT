import { computed, onScopeDispose, ref } from 'vue'
import { listProjectFiles, requestProjectFileParsing } from './api'
import type { ProjectFileParseResult, ProjectFileResponse } from './types'
import { errorMessage } from '@/shared/utils/format'

type ParsePhase = 'idle' | 'preparing' | 'parsing' | 'publishing' | 'finished' | 'error'

export function useFileParsing(projectId: string, onFiles: (files: ProjectFileResponse[]) => void) {
  const busy = ref(false)
  const phase = ref<ParsePhase>('idle')
  const total = ref(0)
  const completed = ref(0)
  const error = ref('')
  const progressError = ref('')
  const result = ref<ProjectFileParseResult | null>(null)
  const percentage = computed(() => phase.value === 'finished'
    ? 100
    : total.value ? Math.min(100, Math.floor(completed.value / total.value * 100)) : 0)
  let active = true
  let generation = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  let readController: AbortController | undefined

  function stopPolling() {
    clearTimeout(timer)
    readController?.abort()
  }

  onScopeDispose(() => {
    active = false
    generation++
    stopPolling()
  })

  function reset() {
    if (busy.value) return false
    generation++
    stopPolling()
    phase.value = 'idle'
    total.value = completed.value = 0
    error.value = progressError.value = ''
    result.value = null
    return true
  }

  async function start(fileIds?: number[]) {
    // 同步占用入口，避免弹窗确认与页面入口在首个请求返回前重复提交。
    if (busy.value || phase.value !== 'idle' || !active) return
    busy.value = true
    phase.value = 'preparing'
    const current = ++generation
    const isCurrent = () => active && current === generation
    const ids = fileIds ? [...fileIds] : undefined
    try {
      readController = new AbortController()
      const before = await listProjectFiles(projectId, readController.signal)
      if (!isCurrent()) return
      onFiles(before)
      // 与后端候选规则一致：普通解析最多尝试 3 次，定向重试允许重新解析已有详情。
      const candidates = before.filter(file => file.status === 'active'
        && file.uploadStatus === 'success' && file.businessCode !== 'system'
        && (ids ? ids.includes(file.id) : file.detailRef === null && file.parseAttempts < 3))
      total.value = candidates.length
      phase.value = candidates.length ? 'parsing' : 'publishing'
      const processed = new Set<number>()

      async function poll() {
        if (!isCurrent()) return
        readController = new AbortController()
        try {
          const files = await listProjectFiles(projectId, readController.signal)
          if (!isCurrent()) return
          onFiles(files)
          const byId = new Map(files.map(file => [file.id, file]))
          // 尝试次数在成功、失败落库时都会递增，不能用历史解析状态计算本轮进度。
          for (const candidate of candidates) {
            const file = byId.get(candidate.id)
            if (file && file.contentHash === candidate.contentHash
              && file.lockVersion === candidate.lockVersion
              && file.parseAttempts > candidate.parseAttempts) processed.add(file.id)
          }
          completed.value = processed.size
          if (completed.value === total.value) phase.value = 'publishing'
          progressError.value = ''
        } catch (e) {
          if (isCurrent()) progressError.value = `进度暂时无法更新：${errorMessage(e)}。解析请求仍在等待，请勿重复提交。`
        } finally {
          if (isCurrent()) timer = setTimeout(poll, 1500)
        }
      }

      timer = setTimeout(poll, 1500)
      const data = await requestProjectFileParsing(projectId, ids)
      if (!isCurrent()) return
      generation++
      stopPolling()
      result.value = data
      total.value = data.candidateCount
      completed.value = data.successCount + data.failureCount
      phase.value = 'finished'
      progressError.value = ''
    } catch (e) {
      if (!isCurrent()) return
      generation++
      stopPolling()
      phase.value = 'error'
      error.value = `${errorMessage(e)}；请刷新文件状态核对结果后再决定是否重试。`
    } finally {
      if (active) busy.value = false
    }
  }

  return { busy, phase, total, completed, percentage, error, progressError, result, reset, start }
}
