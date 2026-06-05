<template>
  <div class="page-shell">
    <div class="page-title-row">
      <div>
        <p class="page-eyebrow">Project Detail</p>
        <h1 class="page-title">{{ project?.name || '项目详情' }}</h1>
        <p class="page-description">{{ project?.description || '查看项目基础信息和第 1 阶段任务推进情况。' }}</p>
      </div>
      <n-space>
        <n-button @click="router.push('/projects')">返回项目列表</n-button>
        <n-button type="primary" @click="router.push(`/projects/${projectId}/tasks`)">进入任务看板</n-button>
      </n-space>
    </div>

    <div class="detail-grid" v-if="project">
      <n-card class="glass-card hero-card" :bordered="false">
        <p>项目状态</p>
        <h2>{{ statusLabel(project.status) }}</h2>
        <n-progress type="line" :percentage="progress" color="#2563eb" />
      </n-card>
      <n-card class="glass-card metric-card" :bordered="false">
        <span>任务总数</span>
        <strong>{{ project.taskTotal }}</strong>
      </n-card>
      <n-card class="glass-card metric-card" :bordered="false">
        <span>已完成</span>
        <strong>{{ project.doneTaskTotal }}</strong>
      </n-card>
      <n-card class="glass-card metric-card" :bordered="false">
        <span>成员</span>
        <strong>{{ project.memberTotal }}</strong>
      </n-card>
    </div>

    <n-card class="glass-card" :bordered="false" v-if="project">
      <n-descriptions label-placement="left" :column="2" bordered>
        <n-descriptions-item label="项目编码">{{ project.code || '未设置' }}</n-descriptions-item>
        <n-descriptions-item label="负责人">{{ project.ownerName }}</n-descriptions-item>
        <n-descriptions-item label="计划开始">{{ project.startDate }}</n-descriptions-item>
        <n-descriptions-item label="计划结束">{{ project.endDate }}</n-descriptions-item>
      </n-descriptions>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getProjectDetail } from '@/modules/project/api'
import type { ProjectDetail, ProjectStatus } from '@/modules/project/types'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const project = ref<ProjectDetail | null>(null)

const progress = computed(() => {
  if (!project.value?.taskTotal) return 0
  return Math.round((project.value.doneTaskTotal / project.value.taskTotal) * 100)
})

onMounted(async () => {
  project.value = await getProjectDetail(projectId)
})

function statusLabel(status: ProjectStatus) {
  const map: Record<ProjectStatus, string> = {
    not_started: '未开始',
    running: '进行中',
    paused: '已暂停',
    delayed: '已延期',
    done: '已完成',
    archived: '已归档',
  }
  return map[status]
}
</script>

<style scoped>
.detail-grid {
  display: grid;
  grid-template-columns: 2fr repeat(3, 1fr);
  gap: 18px;
}

.hero-card p,
.metric-card span {
  margin: 0;
  color: #64748b;
}

.hero-card h2 {
  margin: 10px 0 18px;
  font-size: 32px;
  letter-spacing: -0.05em;
}

.metric-card {
  min-height: 150px;
}

.metric-card strong {
  display: block;
  margin-top: 18px;
  color: #0f172a;
  font-size: 42px;
  letter-spacing: -0.06em;
}
</style>
