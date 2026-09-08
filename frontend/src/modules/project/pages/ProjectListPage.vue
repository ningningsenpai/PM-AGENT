<template>
  <div class="page-shell">
    <div class="page-title-row">
      <div>
        <p class="page-eyebrow">Projects</p>
        <h1 class="page-title">项目工作台</h1>
        <p class="page-description">用一张轻量列表观察项目状态，并进入任务看板推进执行。</p>
      </div>
      <n-button type="primary" @click="openCreateModal">新建项目</n-button>
    </div>

    <div class="project-grid">
      <n-card
        v-for="project in projectStore.projects"
        :key="project.id"
        class="project-card glass-card"
        :bordered="false"
        hoverable
        @click="goDetail(project.id)"
      >
        <div class="project-card-head">
          <n-tag :type="statusType(project.status)" round>{{ statusLabel(project.status) }}</n-tag>
          <span class="project-code">{{ project.code || '未设置编码' }}</span>
        </div>
        <h2>{{ project.name }}</h2>
        <p>{{ project.description }}</p>
        <div class="project-progress">
          <div>
            <strong>{{ project.doneTaskTotal }}/{{ project.taskTotal }}</strong>
            <span>任务完成</span>
          </div>
          <n-progress
            type="line"
            :percentage="progress(project.doneTaskTotal, project.taskTotal)"
            :show-indicator="false"
            color="#2563eb"
          />
        </div>
        <div class="project-meta">
          <span>负责人：{{ project.ownerName }}</span>
          <span>{{ project.startDate }} → {{ project.endDate }}</span>
        </div>
      </n-card>
    </div>

    <n-modal v-model:show="showCreate" preset="card" title="新建项目" class="create-modal">
      <n-form :model="createForm" label-placement="top">
        <n-form-item label="项目名称">
          <n-input v-model:value="createForm.name" placeholder="例如：PM-Agent 平台 MVP" />
        </n-form-item>
        <n-form-item label="项目编码">
          <n-input v-model:value="createForm.code" placeholder="例如：PM-MVP" />
        </n-form-item>
        <n-form-item label="项目说明">
          <n-input v-model:value="createForm.description" type="textarea" placeholder="说明项目目标和范围" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showCreate = false">取消</n-button>
          <n-button type="primary" :loading="creating" @click="handleCreate">创建</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { createProject } from '@/modules/project/api'
import { useProjectStore } from '@/modules/project/store'
import type { ProjectStatus } from '@/modules/project/types'

const router = useRouter()
const message = useMessage()
const projectStore = useProjectStore()
const showCreate = ref(false)
const creating = ref(false)
const createForm = reactive({
  name: '',
  code: '',
  description: '',
})

onMounted(() => {
  projectStore.loadProjects()
})

function progress(done: number, total: number) {
  return total ? Math.round((done / total) * 100) : 0
}

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

function statusType(status: ProjectStatus) {
  if (status === 'running') return 'success'
  if (status === 'delayed') return 'error'
  if (status === 'paused') return 'warning'
  return 'default'
}

function openCreateModal() {
  showCreate.value = true
}

async function handleCreate() {
  if (!createForm.name.trim()) {
    message.warning('请输入项目名称')
    return
  }

  creating.value = true
  try {
    const project = await createProject(createForm)
    message.success('项目创建成功')
    showCreate.value = false
    await projectStore.loadProjects()
    await router.push(`/projects/${project.id}`)
  } finally {
    creating.value = false
  }
}

function goDetail(id: string) {
  router.push(`/projects/${id}`)
}
</script>

<style scoped>
.project-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.project-card {
  cursor: pointer;
}

.project-card-head,
.project-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.project-code,
.project-meta {
  color: #64748b;
  font-size: 13px;
}

.project-card h2 {
  margin: 18px 0 10px;
  color: #0f172a;
  font-size: 22px;
  letter-spacing: -0.04em;
}

.project-card p {
  min-height: 48px;
  margin: 0;
  color: #64748b;
  line-height: 1.7;
}

.project-progress {
  display: grid;
  gap: 10px;
  margin: 24px 0;
}

.project-progress strong {
  margin-right: 8px;
  color: #0f172a;
}

.project-progress span {
  color: #64748b;
}

.create-modal {
  width: 520px;
}
</style>
