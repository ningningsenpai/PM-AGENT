<template>
  <div class="page-shell">
    <div class="page-title-row">
      <div>
        <p class="page-eyebrow">Task Board</p>
        <h1 class="page-title">任务看板</h1>
        <p class="page-description">任务管理暂未开放，文件解析结果不会自动生成任务。</p>
      </div>
      <n-button type="primary" :disabled="!useMock" @click="showCreate = true">新建任务</n-button>
    </div>

    <n-alert v-if="!useMock" type="info">任务创建、状态流转和历史记录暂未开放。以下仅展示看板结构。</n-alert><div class="board-grid">
      <section v-for="status in taskStatusOptions" :key="status.value" class="board-column">
        <div class="column-head">
          <span class="status-dot" :style="{ background: status.tone }" />
          <strong>{{ status.label }}</strong>
          <em>{{ useMock ? groupedTasks[status.value]?.length || 0 : '—' }}</em>
        </div>

        <article v-for="task in groupedTasks[status.value]" :key="task.id" class="task-card glass-card">
          <div class="task-card-title">
            <n-tag size="small" :type="priorityType(task.priority)">{{ task.priority.toUpperCase() }}</n-tag>
            <span>{{ task.dueDate || '暂无截止日期' }}</span>
          </div>
          <h3>{{ task.title }}</h3>
          <p>{{ task.description }}</p>
          <div class="task-card-footer">
            <span>{{ task.assigneeName || '未分配' }}</span>
            <n-select
              :value="task.status"
              :options="selectOptions"
              size="small"
              class="status-select"
              @update:value="(value: TaskStatus) => handleStatusChange(task.id, value)"
            />
          </div>
        </article>
      </section>
    </div>

    <n-modal v-model:show="showCreate" preset="card" title="新建任务" class="create-modal">
      <n-form :model="createForm" label-placement="top">
        <n-form-item label="任务标题">
          <n-input v-model:value="createForm.title" placeholder="请输入任务标题" />
        </n-form-item>
        <n-form-item label="任务说明">
          <n-input v-model:value="createForm.description" type="textarea" placeholder="说明任务目标和完成标准" />
        </n-form-item>
        <n-form-item label="优先级">
          <n-select v-model:value="createForm.priority" :options="priorityOptions" />
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
import { useMock } from '@/mock'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { createTask } from '@/modules/task/api'
import { useTaskStore } from '@/modules/task/store'
import { taskStatusOptions, type TaskPriority, type TaskStatus } from '@/modules/task/types'

const route = useRoute()
const message = useMessage()
const taskStore = useTaskStore()
const projectId = String(route.params.id)
const showCreate = ref(false)
const creating = ref(false)
const createForm = reactive({
  title: '',
  description: '',
  priority: 'p1' as TaskPriority,
})

const selectOptions = taskStatusOptions.map((item) => ({ label: item.label, value: item.value }))
const priorityOptions = [
  { label: 'P0 紧急', value: 'p0' },
  { label: 'P1 高', value: 'p1' },
  { label: 'P2 中', value: 'p2' },
  { label: 'P3 低', value: 'p3' },
]

const groupedTasks = computed<Record<TaskStatus, typeof taskStore.tasks>>(() => {
  return taskStatusOptions.reduce(
    (result, status) => {
      result[status.value] = (useMock ? taskStore.tasks : []).filter((task) => task.status === status.value)
      return result
    },
    {} as Record<TaskStatus, typeof taskStore.tasks>,
  )
})

onMounted(() => {
  if (useMock) void taskStore.loadTasks(projectId)
})

function priorityType(priority: TaskPriority) {
  if (priority === 'p0') return 'error'
  if (priority === 'p1') return 'warning'
  if (priority === 'p2') return 'info'
  return 'default'
}

async function handleStatusChange(id: number, status: TaskStatus) {
  await taskStore.changeTaskStatus(id, status)
  message.success('任务状态已更新')
}

async function handleCreate() {
  if (!createForm.title.trim()) {
    message.warning('请输入任务标题')
    return
  }

  creating.value = true
  try {
    await createTask({
      projectId,
      title: createForm.title,
      description: createForm.description,
      priority: createForm.priority,
    })
    message.success('任务创建成功')
    showCreate.value = false
    createForm.title = ''
    createForm.description = ''
    createForm.priority = 'p1'
    await taskStore.loadTasks(projectId)
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.board-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(190px, 1fr));
  gap: 14px;
  align-items: start;
}

.board-column {
  min-height: 520px;
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.48);
}

.column-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  color: #0f172a;
}

.column-head em {
  margin-left: auto;
  color: #94a3b8;
  font-style: normal;
}

.task-card {
  margin-bottom: 12px;
  padding: 14px;
  border-radius: 18px;
}

.task-card-title,
.task-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.task-card-title span,
.task-card-footer span {
  color: #64748b;
  font-size: 12px;
}

.task-card h3 {
  margin: 12px 0 8px;
  color: #0f172a;
  font-size: 16px;
  line-height: 1.35;
}

.task-card p {
  min-height: 42px;
  margin: 0 0 14px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.status-select {
  width: 96px;
}

.create-modal {
  width: 520px;
}
</style>
