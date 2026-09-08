<template>
  <div class="page-shell">
    <div class="page-title-row">
      <div>
        <p class="eyebrow">个人工作台</p>
        <h1 class="page-title">
          {{ auth.user?.username || '你好' }}，从项目资料开始
        </h1>
        <p class="page-description">
          同步资料、核对事实，把项目讨论沉淀为下一次工作的依据。
        </p>
      </div>
      <n-button type="primary" @click="$router.push('/projects?create=1')"
        >新建项目</n-button
      >
    </div>
    <RequestError :message="store.error" retry @retry="store.loadProjects()" />
    <EmptyProject
      v-if="!store.projects.length && !store.loading && !store.error"
    />
    <template v-else>
      <div class="overview-metrics">
        <section
          v-for="metric in metrics"
          :key="metric.label"
          class="surface metric"
        >
          <span>{{ metric.label }}</span
          ><strong>{{
            store.loading || store.error ? '—' : metric.value
          }}</strong
          ><small>{{ metric.description }}</small>
        </section>
      </div>
      <section class="surface overview-journey">
        <div>
          <p class="eyebrow">下一步</p>
          <h2>把资料连接到项目决策</h2>
          <p class="muted">选择一个项目，即可查看文件、会话和已生成报告。</p>
        </div>
        <div class="journey-links">
          <RouterLink v-for="step in steps" :key="step.title" :to="step.to"
            ><span>{{ step.number }}</span
            ><b>{{ step.title }}</b
            ><small>{{ step.description }}</small></RouterLink
          >
        </div>
      </section>
      <div class="overview-columns">
        <section class="surface padded">
          <div class="page-title-row">
            <h2>项目列表</h2>
            <RouterLink to="/projects">全部项目 →</RouterLink>
          </div>
          <RouterLink
            v-for="project in store.projects.slice(0, 5)"
            :key="project.id"
            :to="'/projects/' + project.id"
            class="overview-row"
            ><span
              ><b>{{ project.projectName }}</b
              ><small>{{ formatDate(project.updatedAt) }}</small></span
            ><ProjectStatus :status="project.status"
          /></RouterLink>
        </section>
        <section class="surface padded">
          <div class="page-title-row">
            <div>
              <h2>{{ selected?.projectName || '项目摘要' }}</h2>
              <p class="muted">以下数据仅属于当前选中项目</p>
            </div>
            <n-button text :loading="loading" @click="loadSummary"
              >刷新</n-button
            >
          </div>
          <RequestError :message="error" />
          <div class="summary-metrics">
            <div>
              <strong>{{
                loading || files === null ? '—' : files.length
              }}</strong
              ><span>项目文件</span>
            </div>
            <div>
              <strong>{{
                loading || files === null
                  ? '—'
                  : files.filter((f) => f.analysisStatus === 'success').length
              }}</strong
              ><span>解析成功</span>
            </div>
            <div>
              <strong>{{
                loading || reports === null ? '—' : reports.length
              }}</strong
              ><span>已生成报告</span>
            </div>
          </div>
          <RouterLink
            v-for="report in (reports || []).slice(0, 3)"
            :key="report.id"
            :to="'/projects/' + selected?.id + '/reports?report=' + report.id"
            class="overview-row"
            ><span
              ><b>{{ report.kind === 'risk' ? '风险报告' : '开发报告' }}</b
              ><small>{{ formatDate(report.createdAt) }}</small></span
            ><span>→</span></RouterLink
          >
          <p v-if="reports?.length === 0" class="muted">
            尚无报告，可从报告中心生成。
          </p>
        </section>
      </div>
      <p class="muted">任务完成率、风险记录数量和全局动态暂未提供。</p>
    </template>
  </div>
</template>
<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { useProjectStore } from '@/modules/project/store'
import { useAuthStore } from '@/stores/auth'
import { listProjectFiles } from '@/modules/project/api'
import type { ProjectFileResponse } from '@/modules/project/types'
import { listReports, type Report } from '@/modules/report/api'
import EmptyProject from '@/shared/components/empty-project.vue'
import RequestError from '@/shared/components/request-error.vue'
import ProjectStatus from '@/shared/components/project-status.vue'
import { errorMessage, formatDate } from '@/shared/utils/format'
const store = useProjectStore()
const auth = useAuthStore()
const loading = ref(false)
const error = ref('')
const files = ref<ProjectFileResponse[] | null>(null)
const reports = ref<Report[] | null>(null)
const selected = computed(() =>
  store.projects.find((p) => p.id === store.currentProjectId),
)
const metrics = computed(() => [
  {
    label: '项目总数',
    value: store.projects.length,
    description: '当前账号可访问的项目',
  },
  {
    label: '已初始化',
    value: store.projects.filter((p) => p.status === 'active').length,
    description: '项目空间已准备就绪',
  },
  {
    label: '待完成初始化',
    value: store.projects.filter((p) => p.status !== 'active').length,
    description: '初始化中或初始化失败',
  },
])
const steps = computed(() => [
  {
    number: '01',
    title: '同步与解析',
    description: '准备项目资料',
    to: selected.value ? '/projects/' + selected.value.id : '/projects',
  },
  {
    number: '02',
    title: '与 PM 助手讨论',
    description: '从事实出发提问',
    to: selected.value
      ? '/projects/' + selected.value.id + '/assistant'
      : '/workspace/assistant',
  },
  {
    number: '03',
    title: '生成项目报告',
    description: '保留结论与来源',
    to: selected.value
      ? '/projects/' + selected.value.id + '/reports'
      : '/workspace/reports',
  },
])
let active = true
let generation = 0
onScopeDispose(() => {
  active = false
  generation++
})
async function loadSummary() {
  const current = ++generation
  files.value = null
  reports.value = null
  error.value = ''
  loading.value = false
  if (!selected.value) return
  const projectId = selected.value.id
  loading.value = true
  const results = await Promise.allSettled([
    listProjectFiles(projectId),
    listReports(projectId),
  ])
  if (!active || generation !== current) return
  if (results[0].status === 'fulfilled') files.value = results[0].value
  else error.value = errorMessage(results[0].reason)
  if (results[1].status === 'fulfilled') reports.value = results[1].value
  else
    error.value = [error.value, errorMessage(results[1].reason)]
      .filter(Boolean)
      .join('；')
  loading.value = false
}
watch(
  () => selected.value?.id,
  () => void loadSummary(),
  { immediate: true },
)
</script>
<style scoped>
.overview-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
.metric {
  padding: 24px 28px;
  border-top: 3px solid var(--pm-blue);
}
.metric:nth-child(2) {
  border-top-color: var(--pm-green);
}
.metric:nth-child(3) {
  border-top-color: var(--pm-yellow);
}
.metric span,
.metric small {
  display: block;
  color: var(--pm-text-secondary);
  font-size: 13px;
}
.metric strong {
  display: block;
  font-size: 38px;
  margin: 16px 0 8px;
  font-weight: 650;
}
.overview-journey {
  padding: 28px;
  display: flex;
  gap: 30px;
  align-items: center;
}
.overview-journey h2,
.overview-columns h2 {
  margin: 0;
  font-size: 20px;
}
.journey-links {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  flex: 1;
}
.journey-links a {
  display: grid;
  gap: 10px;
  text-decoration: none;
  background: var(--pm-bg);
  border-radius: 12px;
  padding: 18px;
}
.journey-links span {
  color: var(--pm-green-dark);
  font-size: 12px;
}
.journey-links b {
  font-size: 14px;
  color: var(--pm-text);
}
.journey-links small {
  font-size: 12px;
  color: var(--pm-text-secondary);
}
.overview-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.overview-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 20px 0;
  border-bottom: 1px solid var(--pm-border-light);
  text-decoration: none;
  color: var(--pm-text);
}
.overview-row small {
  display: block;
  color: var(--pm-text-secondary);
  font-size: 12px;
  margin-top: 6px;
}
.summary-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
  margin: 20px 0;
}
.summary-metrics strong {
  display: block;
  font-size: 26px;
  color: var(--pm-blue-dark);
}
.summary-metrics span {
  font-size: 12px;
  color: var(--pm-text-secondary);
}
</style>
