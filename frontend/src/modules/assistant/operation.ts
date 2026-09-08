import { computed, onScopeDispose, ref } from 'vue'
import { RequestError } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { errorMessage } from '@/shared/utils/format'
import { executeOperation, getRun } from './api'
import type { OperationKind, PendingOperation, Run } from './types'

export function useOperation(projectId:string,conversationId?:string) {
  const userId=useAuthStore().user?.id
  const token=useAuthStore().token
  const storageKey=`pm-operation:${userId}:${projectId}:${conversationId || 'reports'}`
  const pending=ref<PendingOperation|null>(null); const run=ref<Run|null>(null); const busy=ref(false); const error=ref('')
  let active=true; let timer:ReturnType<typeof setTimeout>|undefined
  const valid=()=>active && useAuthStore().token===token
  try { const raw=sessionStorage.getItem(storageKey); if(raw) { const item=JSON.parse(raw); if(typeof item.key==='string' && ['chat','learn','development','risk'].includes(item.kind)) pending.value=item } } catch { error.value='无法恢复本地运行记录，请从历史消息或报告查看结果' }
  const unresolved=computed(()=>Boolean(pending.value && !pending.value.terminal))
  onScopeDispose(()=>{active=false;clearTimeout(timer)})
  function save() { if(!valid()) return; try { if(pending.value) sessionStorage.setItem(storageKey,JSON.stringify(pending.value)) } catch { error.value='无法保存恢复信息，请记录运行编号后再离开页面' } }
  function accept(value:Run) {
    if(!valid()) return
    if(value.projectId!==projectId || (conversationId && value.conversationId!==conversationId)) { error.value='运行不属于当前项目或会话'; return }
    run.value=value
    if(pending.value) { pending.value.runId=value.runId; pending.value.terminal=value.status!=='running'; if(pending.value.terminal) pending.value.payload={}; save() }
    clearTimeout(timer)
    if(value.status==='running') timer=setTimeout(()=>void recover(),3000)
  }
  async function submit() {
    if(!pending.value || busy.value) return
    const operation=pending.value; busy.value=true; error.value=''
    try { accept(await executeOperation(projectId,conversationId,operation.kind,operation.payload,operation.key)) }
    catch(e) {
      if(!valid()) return
      error.value=errorMessage(e)
      // 明确拒绝的请求可修正后新建；传输中断保留原请求和幂等键供恢复。
      if(e instanceof RequestError && !e.uncertain && e.code!==10003) { operation.terminal=true; operation.payload={}; save() }
    } finally { if(valid()) busy.value=false }
  }
  async function start(kind:OperationKind,payload:Record<string,unknown>={}) {
    if(busy.value || unresolved.value) return
    pending.value={key:crypto.randomUUID(),kind,payload,terminal:false};run.value=null;save();await submit()
  }
  async function recover() {
    if(busy.value || !pending.value) return
    if(!pending.value.runId) { await submit();return }
    busy.value=true;error.value=''
    try { accept(await getRun(pending.value.runId)) } catch(e) { if(valid()) error.value=errorMessage(e) }
    finally { if(valid()) busy.value=false }
  }
  async function track(id:string,kind:OperationKind='chat') {
    if(busy.value || (unresolved.value && pending.value?.runId!==id)) return
    pending.value={key:crypto.randomUUID(),kind,payload:{},runId:id,terminal:false};save();await recover()
  }
  return {pending,run,busy,error,unresolved,start,recover,track}
}

