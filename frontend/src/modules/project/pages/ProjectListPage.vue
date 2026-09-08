<template>
  <div class="page-shell">
    <div class="page-title-row">
      <div>
        <p class="eyebrow">项目空间</p>
        <h1 class="page-title">项目管理</h1>
        <p class="page-description">
          集中管理项目资料，为问答和报告准备可信上下文。
        </p>
      </div>
      <n-button type="primary" size="large" @click="showCreate = true"
        >新建项目</n-button
      >
    </div>
    <RequestError :message="store.error" retry @retry="store.loadProjects()" />
    <section class="surface toolbar">
      <n-input
        v-model:value="query"
        placeholder="按项目名称搜索"
        clearable
        style="max-width: 340px"
      /><n-select
        v-model:value="status"
        :options="statuses"
        style="width: 180px"
      /><span class="muted">{{ filtered.length }} 个项目</span
      ><n-button :loading="store.loading" @click="store.loadProjects()"
        >刷新</n-button
      >
    </section>
    <n-spin :show="store.loading">
      <EmptyProject
        v-if="!store.projects.length && !store.loading && !store.error"
      />
      <div v-else-if="filtered.length" class="project-grid">
        <RouterLink
          v-for="project in filtered"
          :key="project.id"
          :to="`/projects/${project.id}`"
          class="surface project-card"
        >
          <div class="project-card-top">
            <ProjectStatus :status="project.status" /><span class="muted"
              >项目</span
            >
          </div>
          <h2>{{ project.projectName }}</h2>
          <p class="muted">源码、文档、会话与报告的独立空间</p>
          <dl>
            <dt>创建时间</dt>
            <dd>{{ formatDate(project.createdAt) }}</dd>
            <dt>最近更新</dt>
            <dd>{{ formatDate(project.updatedAt) }}</dd>
          </dl>
          <div class="project-card-bottom">
            <span>进入项目</span><span aria-hidden="true">→</span>
          </div>
        </RouterLink>
      </div>
      <n-empty
        v-else-if="!store.loading && !store.error"
        description="没有符合条件的项目"
        class="surface padded"
      />
    </n-spin>
    <CreateProjectDialog v-model:show="showCreate" @created="created" />
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore } from '../store'
import CreateProjectDialog from '../components/create-project-dialog.vue'
import ProjectStatus from '@/shared/components/project-status.vue'
import EmptyProject from '@/shared/components/empty-project.vue'
import RequestError from '@/shared/components/request-error.vue'
import { formatDate } from '@/shared/utils/format'
const store = useProjectStore()
const route = useRoute()
const router = useRouter()
const query = ref('')
const status = ref('all')
const showCreate = ref(route.query.create === '1')
const statuses = [
  { label: '全部状态', value: 'all' },
  { label: '已初始化', value: 'active' },
  { label: '初始化中', value: 'initializing' },
  { label: '初始化失败', value: 'init_failed' },
]
const filtered = computed(() =>
  store.projects.filter(
    (p) =>
      p.projectName.toLowerCase().includes(query.value.trim().toLowerCase()) &&
      (status.value === 'all' || status.value === p.status),
  ),
)
watch(
  () => route.query.create,
  (value) => {
    if (value === '1') showCreate.value = true
  },
)
onMounted(() => {
  void store.loadProjects()
})
async function created(id: string) {
  await store.loadProjects(true)
  store.currentProjectId = id
  await router.push(`/projects/${id}`)
}
</script>
<style scoped>
.project-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
}
.project-card {
  text-decoration: none;
  color: inherit;
  padding: 24px;
  transition:
    box-shadow 0.15s,
    border-color 0.15s;
  border-top: 3px solid var(--pm-blue);
}
.project-card:hover {
  border-color: var(--pm-blue);
  box-shadow: 0 12px 28px #1320330d;
}
.project-card-top,
.project-card-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
h2 {
  font-size: 21px;
  margin: 22px 0 10px;
  overflow-wrap: anywhere;
}
dl {
  font-size: 12px;
  margin: 28px 0;
}
dt {
  color: var(--pm-text-muted);
  margin-top: 10px;
}
dd {
  margin: 4px 0 0;
}
.project-card-bottom {
  border-top: 1px solid var(--pm-border-light);
  padding-top: 18px;
  color: var(--pm-blue-dark);
  font-weight: 600;
}
@media (max-width: 1400px) {
  .project-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
