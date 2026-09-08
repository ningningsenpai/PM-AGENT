<template>
  <div class="conversation-workspace">
    <div class="conversation-body surface">
      <header class="conversation-head"><div><h2>{{ conversation.title }}</h2><small class="muted">会话记录自动保存 · 普通问答</small></div><n-button secondary type="success" :disabled="locked || !messages.some(m=>m.role==='user')" @click="learn">学习本会话</n-button></header>
      <div class="messages">
        <RequestError :message="error" retry @retry="load" />
        <div v-if="loading" class="muted">正在读取历史消息…</div>
        <div v-else-if="!messages.length" class="chat-welcome"><img :src="assistantImage" alt="PM 助手" /><h2>从项目里的一个问题开始</h2><p>我会根据已解析的资料回答，并保留工具调用记录。</p><n-space justify="center"><n-button v-for="prompt in prompts" :key="prompt" @click="draft=prompt">{{ prompt }}</n-button></n-space></div>
        <article v-for="item in messages" :key="item.id" :class="['message',item.role==='user'?'user':'assistant']"><div class="message-meta">{{ item.role==='user'?'你':'PM 助手' }} · {{ formatDate(item.createdAt) }}<n-button v-if="item.runId" text size="tiny" :disabled="operation.unresolved.value || operation.busy.value" @click="operation.track(item.runId)">查看运行</n-button></div><SafeMarkdown :content="item.content" /></article>
      </div>
      <div class="composer">
        <RequestError :message="operation.error.value" />
        <n-alert v-if="operation.unresolved.value" type="info"><span>{{ operation.run.value?.status==='running'?'正在处理，完成后自动更新。':'有一项操作尚未确认结果。请先恢复，避免重复执行。' }}</span><n-button size="small" :loading="operation.busy.value" @click="operation.recover">查询 / 恢复</n-button></n-alert>
        <n-input v-model:value="draft" type="textarea" placeholder="输入项目问题，Ctrl + Enter 发送" :maxlength="16000" show-count :autosize="{minRows:3,maxRows:8}" :disabled="locked" @keydown.ctrl.enter.prevent="send" />
        <div class="composer-foot"><small>回答可能存在遗漏，请结合来源核对；学习需要手动确认。</small><n-button type="primary" :loading="operation.busy.value" :disabled="locked || !draft.trim()" @click="send">发送消息</n-button></div>
      </div>
    </div>
    <aside class="surface padded"><RunDetail :run="operation.run.value" /><div class="assistant-note"><h4>本轮能力</h4><p>读取项目资料、查询上下文、生成建议。任务变更和审批执行暂未开放。</p><p>学习游标：{{ conversation.learnedMessageId==='0'?'尚未学习':conversation.learnedMessageId }}</p></div></aside>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onScopeDispose, ref, watch } from 'vue'
import { useDialog } from 'naive-ui'
import { listMessages } from '../api'
import { useOperation } from '../operation'
import type { ChatMessage, Conversation } from '../types'
import SafeMarkdown from '@/shared/components/safe-markdown.vue'
import RequestError from '@/shared/components/request-error.vue'
import RunDetail from './run-detail.vue'
import assistantImage from '@/assets/figma/assistant.png'
import { errorMessage, formatDate } from '@/shared/utils/format'
const props=defineProps<{projectId:string;conversation:Conversation;disabled?:boolean}>()
const emit=defineEmits<{changed:[];busy:[value:boolean]}>()
const operation=useOperation(props.projectId,props.conversation.id);const dialog=useDialog()
const messages=ref<ChatMessage[]>([]);const loading=ref(false);const error=ref('');const draft=ref('')
const prompts=['概括当前项目的主要模块','项目目前有哪些值得关注的风险？']
const locked=computed(()=>operation.busy.value||operation.unresolved.value||Boolean(props.disabled))
let active=true;let generation=0;onScopeDispose(()=>{active=false;generation++})
watch(()=>operation.busy.value,value=>emit('busy',value),{flush:'sync'})
async function load() {const current=++generation;loading.value=true;error.value='';try {const data=await listMessages(props.conversation.id);if(active && current===generation)messages.value=data}catch(e){if(active && current===generation)error.value=errorMessage(e)}finally{if(active && current===generation)loading.value=false}}
onMounted(async()=>{await load();if(!active)return;if(operation.pending.value?.runId)void operation.recover();else if(!operation.pending.value && props.conversation.activeRunId)void operation.track(props.conversation.activeRunId)})
watch(()=>operation.run.value,run=>{if(run && run.status!=='running'){void load();emit('changed')} })
async function send() {if(locked.value||!draft.value.trim())return;const content=draft.value.trim();draft.value='';await operation.start('chat',{content});if(active && operation.error.value && !operation.unresolved.value)draft.value=content}
function learn() {if(locked.value)return;dialog.info({title:'学习本会话',content:'从尚未学习的用户消息中提取词条、偏好和项目记忆，供后续问答使用。此操作会调用模型。',positiveText:'确认学习',negativeText:'取消',onPositiveClick:()=>operation.start('learn')})}
</script>
<style scoped>
.conversation-workspace {display:grid;grid-template-columns:minmax(420px,1fr) 272px;gap:18px;min-width:0;} .conversation-body {display:flex;flex-direction:column;min-height:680px;overflow:hidden;}
.conversation-head {padding:22px;border-bottom:1px solid var(--pm-border);display:flex;align-items:center;justify-content:space-between;gap:12px;} h2 {font-size:17px;margin:0 0 6px;}
.messages {flex:1;padding:24px;display:flex;flex-direction:column;gap:24px;max-height:650px;overflow:auto;} .message {padding:18px;border:1px solid var(--pm-border);border-radius:14px;} .message.user {background:var(--pm-blue-soft);border-color:#dde9fb;margin-left:30px;} .message.assistant {margin-right:16px;}
.message-meta {display:flex;gap:12px;align-items:center;color:var(--pm-text-secondary);font-size:11px;margin-bottom:12px;} .message-meta .n-button {margin-left:auto;}
.chat-welcome {text-align:center;margin:auto;padding:32px 0;} .chat-welcome img {width:110px;height:110px;object-fit:contain;} .chat-welcome p {color:var(--pm-text-secondary);font-size:13px;margin-bottom:24px;}
.composer {padding:18px;border-top:1px solid var(--pm-border);display:grid;gap:12px;}.composer-foot {display:flex;justify-content:space-between;align-items:center;gap:12px;}.composer-foot small {color:var(--pm-text-muted);font-size:11px;}
.assistant-note {margin-top:28px;padding:16px;background:var(--pm-green-soft);border-radius:12px;color:var(--pm-text-secondary);font-size:12px;line-height:1.8;overflow-wrap:anywhere;} .assistant-note h4 {margin:0;color:var(--pm-green-dark);}
@media(max-width:1450px){.conversation-workspace{grid-template-columns:minmax(360px,1fr);} .conversation-workspace>aside{margin-top:0;}}
</style>

