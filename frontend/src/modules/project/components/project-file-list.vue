<template>
  <section class="surface padded file-panel">
    <div class="page-title-row"><div><h2>项目文件与解析</h2><p class="muted">同步文件后，解析内容供 PM 助手检索；解析不会生成任务。</p></div><n-space><n-button :loading="loading" :disabled="busy || disabled" @click="load">刷新列表</n-button><n-button :disabled="busy || disabled || !selected.length" @click="parse(true)">重试所选（{{ selected.length }}）</n-button><n-button type="primary" :loading="busy" :disabled="disabled || !files.length" @click="parse(false)">解析项目文件</n-button></n-space></div>
    <RequestError :message="error" />
    <n-alert v-if="busy" type="info">正在解析，请保持页面打开。模型处理可能需要数分钟，完成后会更新结果。</n-alert>
    <n-alert v-if="result" :type="result.status === 'partial' || result.indexStatus === 'failed' || result.specificationStatus === 'failed' ? 'warning' : 'success'" title="解析结果">
      本轮候选 {{ result.candidateCount }} 个，成功 {{ result.successCount }} 个，失败 {{ result.failureCount }} 个。
      项目规范：{{ {updated:'已更新',kept:'保持原有内容',failed:'更新失败'}[result.specificationStatus] }}；
      文件索引：{{ result.indexStatus === 'updated' ? '已更新' : '发布失败' }}。
      <p v-if="result.runId" class="muted">运行编号：{{ result.runId }}</p>
      <ul v-if="result.failures.length"><li v-for="failure in result.failures" :key="failure.fileId">{{ failure.relativePath }}：{{ failure.errorMessage }}（{{ failure.errorCode }}）</li></ul>
    </n-alert>
    <div class="toolbar"><n-input v-model:value="query" clearable placeholder="查找文件路径" style="max-width:320px" /><n-select v-model:value="status" :options="statuses" style="width:180px" /><span class="muted">{{ files.length }} 个文件</span></div>
    <n-data-table :columns="columns" :data="filtered" :row-key="(row: ProjectFileResponse) => row.id" :checked-row-keys="selected" @update:checked-row-keys="(keys: Array<string | number>) => selected = keys as number[]" :loading="loading" :pagination="{pageSize:10}" :scroll-x="850" />
    <n-modal v-model:show="showRead" preset="card" title="读取原始文件" style="width:620px">
      <p>原始文件可能包含不可信内容。仅在确认来源后打开，临时链接到期后需重新获取。</p>
      <a v-if="readUrl" :href="readUrl" target="_blank" rel="noopener noreferrer">在新标签页读取 {{ readName }}</a>
    </n-modal>
  </section>
</template>
<script setup lang="ts">
import { computed, h, onScopeDispose, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { NButton, NTag, useDialog, useMessage, type DataTableColumns } from 'naive-ui'
import { getFileReadUrl, listProjectFiles, requestProjectFileParsing } from '../api'
import type { ProjectFileResponse, ProjectFileParseResult } from '../types'
import RequestError from '@/shared/components/request-error.vue'
import { errorMessage } from '@/shared/utils/format'
const props = defineProps<{projectId:string;revision?:number;disabled?:boolean}>()
const emit = defineEmits<{busy:[value:boolean]}>()
const files = ref<ProjectFileResponse[]>([]); const selected = ref<number[]>([]); const query = ref(''); const status = ref('all')
const loading = ref(false); const busy = ref(false); const error = ref(''); const result = ref<ProjectFileParseResult|null>(null)
const showRead = ref(false); const readUrl = ref(''); const readName = ref('')
const dialog = useDialog(); const message = useMessage(); let generation = 0; let active = true
onScopeDispose(() => { active = false; generation++ })
watch(busy, value => emit('busy', value), {flush:'sync'})
function guard() { if (busy.value) { message.warning('正在解析文件，请等待操作结束'); return false } }
onBeforeRouteLeave(guard); onBeforeRouteUpdate(guard)
const labels:Record<string,string> = {pending:'待解析',success:'解析成功',failed:'解析失败',unavailable:'不可用'}
const statuses = [{label:'全部解析状态',value:'all'},...Object.entries(labels).map(([value,label])=>({value,label}))]
const filtered = computed(()=>files.value.filter(f=>f.relativePath.toLowerCase().includes(query.value.trim().toLowerCase()) && (status.value==='all'||f.analysisStatus===status.value)))
const columns:DataTableColumns<ProjectFileResponse> = [
  {type:'selection',disabled:()=>busy.value || Boolean(props.disabled)},
  {title:'文件路径',key:'relativePath',minWidth:240,render:row=>h('div',[h('strong',row.relativePath),row.lastErrorMessage ? h('p',{class:'file-error'},row.lastErrorMessage + (row.lastErrorCode ? '（'+row.lastErrorCode+'）' : '')):null])},
  {title:'大小',key:'sizeBytes',width:95,render:row=>row.sizeBytes<1024 ? row.sizeBytes+' B' : (row.sizeBytes/1024).toFixed(1)+' KB'},
  {title:'解析状态',key:'analysisStatus',width:110,render:row=>h(NTag,{size:'small',type:row.analysisStatus==='success'?'success':row.analysisStatus==='failed'?'error':'default'},()=>labels[row.analysisStatus]||row.analysisStatus)},
  {title:'尝试次数',key:'parseAttempts',width:90},
  {title:'操作',key:'action',width:120,render:row=>h(NButton,{size:'small',onClick:()=>read(row)},()=> '读取原文')},
]
async function load() {
  const current = ++generation; loading.value = true; error.value = ''
  try { const data = await listProjectFiles(props.projectId); if(active && current===generation) { files.value=data; selected.value=selected.value.filter(id=>data.some(f=>f.id===id)) } }
  catch(e) { if(active && current===generation) error.value=errorMessage(e) }
  finally { if(active && current===generation) loading.value=false }
}
watch(()=>[props.projectId,props.revision],()=>void load(),{immediate:true})
function parse(targeted:boolean) {
  if(busy.value || props.disabled) return
  if(targeted && selected.value.length>100) { message.warning('一次最多重试 100 个文件'); return }
  const ids = targeted ? [...selected.value] : undefined
  dialog.info({title:targeted?'重新解析所选文件':'解析项目文件',content:targeted?'将重新解析所选文件，可能产生模型调用费用。':'将解析待处理文件并更新项目上下文，可能产生模型调用费用。',positiveText:'开始解析',negativeText:'取消',onPositiveClick:async()=>{
    busy.value=true; error.value=''; result.value=null
    try { const data=await requestProjectFileParsing(props.projectId,ids); if(active) result.value=data }
    catch(e) { if(active) error.value=errorMessage(e)+'；请刷新文件状态核对结果后再决定是否重试。' }
    finally { if(active) { busy.value=false; const operationError=error.value; await load(); if(operationError) error.value=operationError } }
  }})
}
async function read(file:ProjectFileResponse) {
  try { const data=await getFileReadUrl(props.projectId,file.id); const url=new URL(data.url); if(!['https:','http:'].includes(url.protocol)) throw new Error('文件链接格式不受支持'); if(active) {readUrl.value=url.href;readName.value=file.fileName;showRead.value=true} }
  catch(e) { if(active) error.value=errorMessage(e) }
}
</script>
<style scoped>
.file-panel { display:grid;gap:18px; } h2 { margin:0; } :deep(.file-error) { color:#b54708;font-size:12px;overflow-wrap:anywhere; }
</style>

