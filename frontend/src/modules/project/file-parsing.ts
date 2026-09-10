import { computed, onScopeDispose, ref } from 'vue'
import { listProjectFiles, recoverProjectFileParsing, requestProjectFileParsing } from './api'
import type { ProjectFileParseResult, ProjectFileResponse } from './types'
import { RequestError } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { errorMessage } from '@/shared/utils/format'

type ParsePhase = 'idle' | 'preparing' | 'parsing' | 'publishing' | 'finished' | 'error'
interface PendingParseRequest {
  key: string
  fileIds: number[] | null
  startedAt: string
}

export function useFileParsing(projectId: string, onFiles: (files: ProjectFileResponse[]) => void) {
  const userId = useAuthStore().user?.id
  const storageKey = `pm-file-parse:${userId || 'unknown'}:${projectId}`
  const busy = ref(false)
  const phase = ref<ParsePhase>('idle')
  const total = ref(0)
  const completed = ref(0)
  const error = ref('')
  const progressError = ref('')
  const result = ref<ProjectFileParseResult | null>(null)
  const pending = ref<PendingParseRequest | null>(null)
  try {
    const raw = sessionStorage.getItem(storageKey)
    if (raw) {
      const value = JSON.parse(raw)
      if (typeof value.key === 'string'
        && (value.fileIds === null || (Array.isArray(value.fileIds)
          && value.fileIds.every((item: unknown) => typeof item === 'number'
            && Number.isSafeInteger(item))))) {
        pending.value = value
      }
    }
  } catch {
    error.value = '无法恢复上一次文件解析请求，请刷新文件状态后再决定是否重试'
  }
  const hasPending = computed(() => Boolean(pending.value))
  const pendingFileIds = computed(() => pending.value?.fileIds ?? undefined)
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

  function normalizeFileIds(fileIds?: number[]) {
    return fileIds?.length ? [...new Set(fileIds)].sort((left, right) => left - right) : null
  }

  function sameSelection(left: number[] | null, right: number[] | null) {
    return left === null && right === null
      || Boolean(left && right && left.length === right.length
        && left.every((item, index) => item === right[index]))
  }

  function prepareRequest(fileIds?: number[]) {
    const normalized = normalizeFileIds(fileIds)
    if (pending.value) {
      if (!sameSelection(pending.value.fileIds, normalized)) {
        throw new Error('上一次解析结果尚未确认，请先恢复原批次')
      }
      return { key: pending.value.key, fileIds: normalized }
    }
    const request = {
      key: crypto.randomUUID(),
      fileIds: normalized,
      startedAt: new Date().toISOString(),
    }
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(request))
    } catch {
      throw new Error('无法保存解析恢复信息，请检查浏览器存储权限后重试')
    }
    pending.value = request
    return { key: request.key, fileIds: normalized }
  }

  function clearPending() {
    pending.value = null
    try {
      sessionStorage.removeItem(storageKey)
    } catch {
      // 运行结果已经明确时以内存终态为准，存储清理失败不能改写业务结果。
    }
  }

  function finish(data: ProjectFileParseResult) {
    result.value = data
    total.value = data.candidateCount
    completed.value = data.successCount + data.failureCount
    phase.value = data.status === 'success' ? 'finished' : 'error'
    progressError.value = ''
    clearPending()
  }

  async function waitForRecovery(current: number) {
    await new Promise<void>((resolve) => {
      timer = setTimeout(resolve, 2000)
    })
    return active && current === generation
  }

  async function resolvePending(current: number, allowAbsentResend: boolean) {
    const isCurrent = () => active && current === generation
    let resent = false
    while (isCurrent() && pending.value) {
      let recovery
      try {
        recovery = await recoverProjectFileParsing(projectId, pending.value.key)
      } catch (recoveryError) {
        phase.value = 'error'
        error.value = `暂时无法确认原解析结果：${errorMessage(recoveryError)}。恢复信息已保留。`
        return
      }
      if (!isCurrent()) return
      if (recovery.status === 'success' && recovery.result) {
        finish(recovery.result)
        return
      }
      if (recovery.status === 'failed') {
        if (recovery.result) result.value = recovery.result
        phase.value = 'error'
        error.value = `${recovery.error || '本次解析未成功完成'}；可以立即重试，重试将生成新的幂等键。`
        clearPending()
        return
      }
      if (recovery.status === 'running') {
        phase.value = 'parsing'
        if (!await waitForRecovery(current)) return
        continue
      }
      if (recovery.status === 'absent' && allowAbsentResend && !resent) {
        resent = true
        try {
          const data = await requestProjectFileParsing(
            projectId,
            pending.value.fileIds ?? undefined,
            pending.value.key,
          )
          if (isCurrent()) finish(data)
          return
        } catch (resendError) {
          if (resendError instanceof RequestError && resendError.uncertain) continue
          phase.value = 'error'
          error.value = errorMessage(resendError)
          clearPending()
          return
        }
      }
      phase.value = 'error'
      error.value = '原请求未在后端创建，可以重新点击解析。'
      clearPending()
      return
    }
  }

  async function start(fileIds?: number[]) {
    // 同步占用入口，避免弹窗确认与页面入口在首个请求返回前重复提交。
    if (busy.value || phase.value !== 'idle' || !active) return
    busy.value = true
    phase.value = 'preparing'
    const current = ++generation
    const isCurrent = () => active && current === generation
    try {
      const request = prepareRequest(fileIds)
      const ids = request.fileIds ?? undefined
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
      const data = await requestProjectFileParsing(projectId, ids, request.key)
      if (!isCurrent()) return
      generation++
      stopPolling()
      finish(data)
    } catch (e) {
      if (!isCurrent()) return
      stopPolling()
      if (e instanceof RequestError && (e.uncertain || e.code === 10003)) {
        await resolvePending(current, true)
      } else {
        phase.value = 'error'
        error.value = errorMessage(e)
        clearPending()
      }
    } finally {
      if (active) busy.value = false
    }
  }

  async function recover() {
    if (busy.value || !active || !pending.value) return
    busy.value = true
    phase.value = 'preparing'
    error.value = ''
    const current = ++generation
    try {
      await resolvePending(current, true)
    } finally {
      if (active && current === generation) busy.value = false
    }
  }

  return {
    busy,
    phase,
    total,
    completed,
    percentage,
    error,
    progressError,
    result,
    hasPending,
    pendingFileIds,
    reset,
    start,
    recover,
  }
}
