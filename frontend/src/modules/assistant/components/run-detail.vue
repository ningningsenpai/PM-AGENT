<template>
  <section class="run-detail">
    <div class="page-title-row">
      <h3>运行记录</h3>
      <n-tag
        v-if="run"
        :type="
          run.status === 'success'
            ? 'success'
            : run.status === 'failed'
              ? 'error'
              : 'info'
        "
        size="small"
        >{{
          { running: '运行中', success: '完成', failed: '失败' }[run.status]
        }}</n-tag
      >
    </div>
    <n-empty v-if="!run" description="发送消息或生成报告后查看运行记录" />
    <template v-else
      ><p v-if="run.error" class="run-error">{{ run.error }}</p>
      <dl>
        <dt>运行编号</dt>
        <dd>{{ run.runId }}</dd>
        <dt>追踪编号</dt>
        <dd>{{ run.traceId }}</dd>
        <dt>操作</dt>
        <dd>{{ operationLabel }}</dd>
      </dl>
      <n-alert v-if="snapshotFailures.length" type="warning"
        >部分上下文文件未能发布，请在待确认内容或内容管理中核对。
        <p v-for="(item, index) in snapshotFailures" :key="index">
          {{ item }}
        </p></n-alert
      >
      <details v-if="toolCalls.length" open>
        <summary>工具调用与来源（{{ toolCalls.length }}）</summary>
        <details v-for="(tool, index) in toolCalls" :key="index">
          <summary>
            {{ tool.toolName || tool.tool_name || tool.name || '工具调用' }} ·
            {{ tool.success === false ? '失败' : '查看结果' }}
          </summary>
          <pre>{{ JSON.stringify(tool, null, 2) }}</pre>
        </details>
      </details>
      <details>
        <summary>模型与执行记录（{{ run.events.length }}）</summary>
        <pre>{{ JSON.stringify(run.events, null, 2) }}</pre>
      </details>
      <details v-if="run.result.usage">
        <summary>实际用量</summary>
        <pre>{{ JSON.stringify(run.result.usage, null, 2) }}</pre>
      </details>
    </template>
  </section>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { Run } from '../types'
const props = defineProps<{ run: Run | null }>()
const toolCalls = computed(() =>
  Array.isArray(props.run?.result.toolCalls)
    ? (props.run.result.toolCalls as Record<string, unknown>[])
    : [],
)
const operationLabel = computed(
  () =>
    ({ chat: '项目问答', learn_refine: '待确认上下文整理', report: '报告生成' })[
      props.run?.operation || ''
    ] || props.run?.operation,
)
const snapshotFailures = computed(() =>
  Object.values(
    (props.run?.result.snapshots || {}) as Record<
      string,
      { published: boolean; error: string }
    >,
  )
    .filter((s) => !s.published)
    .map((s) => s.error || '快照发布失败'),
)
</script>
<style scoped>
h3 {
  margin: 0 0 16px;
}
dl {
  font-size: 12px;
}
dt {
  color: var(--pm-text-muted);
  margin-top: 12px;
}
dd {
  margin: 4px 0 0;
  overflow-wrap: anywhere;
}
details {
  margin: 16px 0;
  font-size: 12px;
}
summary {
  cursor: pointer;
  color: var(--pm-text-secondary);
}
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: var(--pm-bg);
  padding: 12px;
  max-height: 400px;
  overflow: auto;
}
.run-error {
  color: #b42318;
  overflow-wrap: anywhere;
}
</style>
