<template>
  <div class="page-shell">
    <div class="page-title-row"><div><p class="eyebrow">分析与记录</p><h1 class="page-title">报告中心</h1><p class="page-description">基于当前项目资料生成开发报告与风险报告，保留证据及来源版本。</p></div><RouterLink :to="'/projects/'+projectId">管理项目文件 →</RouterLink></div>
    <section class="surface toolbar"><n-select v-model:value="generateKind" :options="kinds" style="width:180px" /><n-button type="primary" :loading="operation.busy.value" :disabled="operation.unresolved.value" @click="generate">生成报告</n-button><span class="muted">每次生成均保存为独立记录；生成报告可能需要数分钟。</span></section>
    <RequestError :message="operation.error.value" /><n-alert v-if="operation.unresolved.value" type="info">报告运行尚未结束或结果待确认。<n-button :loading="operation.busy.value" size="small" @click="operation.recover">查询 / 恢复原运行</n-button></n-alert>
    <RequestError :message="error" retry @retry="load" />
    <div class="report-grid">
      <aside class="surface report-list"><div class="toolbar"><n-select v-model:value="filter" :options="[{label:'全部报告',value:'all'},...kinds]" /><n-button text :loading="loading" @click="load">刷新</n-button></div>
        <n-empty v-if="!reports.length&&!loading&&!error" description="尚无报告" />
        <button v-for="report in filtered" :key="report.id" :class="['report-item',{selected:report.id===selected?.id}]" @click="open(report.id)"><n-tag size="small" :type="report.kind==='risk'?'warning':'info'">{{ labels[report.kind] }}</n-tag><strong>{{ labels[report.kind] }}</strong><small>{{ formatDate(report.createdAt) }}</small><span>查看正文与来源 →</span></button>
      </aside>
      <section class="surface report-document"><RequestError :message="detailError" /><n-spin :show="detailLoading"><template v-if="selected"><div class="report-document-head"><span class="eyebrow">{{ labels[selected.kind] }} · {{ formatDate(selected.createdAt) }}</span><small class="muted">报告编号 {{ selected.id }}</small></div><SafeMarkdown :content="selected.markdown" /><div class="report-evidence"><h3>来源证据（{{ selected.evidence.length }}）</h3><details v-for="(entry,index) in selected.evidence" :key="String(entry.id||index)"><summary>{{ entry.id }} · {{ entry.logicalPath || (entry.sourceType==='user_statement'?'用户陈述':'文件来源') }}<template v-if="entry.startLine"> · 第 {{ entry.startLine }}～{{ entry.endLine }} 行</template></summary><n-tag v-if="entry.truncated" type="warning" size="small">内容已截断</n-tag><pre>{{ entry.text }}</pre><details><summary>完整来源信息</summary><pre>{{ JSON.stringify(entry,null,2) }}</pre></details></details></div><details><summary>来源版本</summary><pre>{{ JSON.stringify(selected.sourceVersions,null,2) }}</pre></details></template><n-result v-else-if="!detailLoading&&!detailError" status="info" title="让项目现状有据可查" description="选择一份历史报告，或生成当前项目的开发报告、风险报告。" /></n-spin></section>
      <aside class="surface padded"><RunDetail :run="historyRun || operation.run.value" /><p class="muted">报告生成完成后可重新打开。编辑、发布、归档和周报周期暂未开放。</p></aside>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onScopeDispose, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDialog } from 'naive-ui'
import { getReport, listReports, type Report, type ReportKind } from '../api'
import { getRun } from '@/modules/assistant/api'
import type { Run } from '@/modules/assistant/types'
import { useOperation } from '@/modules/assistant/operation'
import RunDetail from '@/modules/assistant/components/run-detail.vue'
import SafeMarkdown from '@/shared/components/safe-markdown.vue'
import RequestError from '@/shared/components/request-error.vue'
import { errorMessage, formatDate } from '@/shared/utils/format'
const route=useRoute();const router=useRouter();const dialog=useDialog();const projectId=String(route.params.id)
const operation=useOperation(projectId);const historyRun=ref<Run|null>(null)
const reports=ref<Report[]>([]);const selected=ref<Report|null>(null);const error=ref('');const detailError=ref('');const loading=ref(false);const detailLoading=ref(false)
const generateKind=ref<ReportKind>(route.query.kind==='risk'?'risk':'development');const filter=ref(route.query.kind==='risk'?'risk':'all')
const labels={development:'开发报告',risk:'风险报告'};const kinds=Object.entries(labels).map(([value,label])=>({value,label}))
const filtered=computed(()=>reports.value.filter(r=>filter.value==='all'||r.kind===filter.value))
let active=true;let generation=0;let detailGeneration=0;onScopeDispose(()=>{active=false;generation++;detailGeneration++})
async function load() {const current=++generation;loading.value=true;error.value='';try{const data=await listReports(projectId);if(active&&current===generation)reports.value=data}catch(e){if(active&&current===generation)error.value=errorMessage(e)}finally{if(active&&current===generation)loading.value=false}}
async function open(id:string,updateUrl=true) {
  const current=++detailGeneration;selected.value=null;detailError.value='';detailLoading.value=true;historyRun.value=null
  try {const report=await getReport(projectId,id);if(!active||current!==detailGeneration)return;selected.value=report;if(updateUrl)await router.replace({query:{...route.query,report:id}});const run=await getRun(report.runId);if(active&&current===detailGeneration)historyRun.value=run}
  catch(e){if(active&&current===detailGeneration)detailError.value=errorMessage(e)}
  finally{if(active&&current===detailGeneration)detailLoading.value=false}
}
function generate(){if(operation.busy.value||operation.unresolved.value)return;dialog.info({title:'生成'+labels[generateKind.value],content:'将读取当前项目资料和已学习内容，并调用模型生成一份新报告。',positiveText:'开始生成',negativeText:'取消',onPositiveClick:()=>{historyRun.value=null;return operation.start(generateKind.value)}})}
watch(()=>operation.run.value,async run=>{if(run&&run.status!=='running'){historyRun.value=null;await load();const report=run.result.report as Report|undefined;if(active&&report?.id){filter.value='all';await open(report.id)}}})
watch(()=>route.query.report,id=>{if(typeof id==='string'&&id!==selected.value?.id)void open(id,false)})
onMounted(async()=>{await load();if(!active)return;if(typeof route.query.report==='string')void open(route.query.report,false);if(operation.pending.value?.runId)void operation.recover()})
</script>
<style scoped>
.report-grid {display:grid;grid-template-columns:230px minmax(390px,1fr) 250px;gap:18px;align-items:start;}.report-list {padding:18px 12px;min-height:600px;display:grid;align-content:start;gap:16px;}.report-item {border:1px solid var(--pm-border);border-radius:12px;padding:18px;text-align:left;background:#fff;display:grid;gap:12px;color:var(--pm-text);cursor:pointer;}.report-item .n-tag{width:fit-content;}.report-item small {color:var(--pm-text-secondary);font-size:11px;}.report-item span:last-child {font-size:12px;color:var(--pm-blue-dark);}.report-item.selected{background:var(--pm-blue-soft);border-color:#c3d9fc;}.report-document {padding:30px;min-height:600px;min-width:0;}.report-document-head {display:grid;gap:8px;border-bottom:1px solid var(--pm-border);margin-bottom:28px;padding-bottom:20px;}.report-evidence {border-top:1px solid var(--pm-border);margin-top:36px;padding-top:20px;} details {margin:16px 0;font-size:12px;} summary {cursor:pointer;color:var(--pm-text-secondary);} pre {white-space:pre-wrap;overflow-wrap:anywhere;background:var(--pm-bg);padding:12px;max-height:400px;overflow:auto;}
@media(max-width:1450px){.report-grid{grid-template-columns:220px minmax(400px,1fr);}.report-grid>aside:last-child{grid-column:2;}}
</style>

