<template>
  <div class="page-shell">
    <RequestError :message="error" retry @retry="load" />
    <n-spin :show="loading">
      <template v-if="project">
        <div class="page-title-row"><div><p class="eyebrow">项目管理 / 项目详情</p><h1 class="page-title">{{ project.projectName }}</h1><p class="page-description">创建于 {{ formatDate(project.createdAt) }} · <ProjectStatus :status="project.status" /></p></div><n-space><n-button @click="$router.push('/projects')">全部项目</n-button><n-button type="error" secondary :disabled="filesBusy" @click="remove">删除项目</n-button></n-space></div>
        <div class="project-links surface"><RouterLink :to="`/projects/${id}/assistant`">打开 PM 助手 <span>基于资料提问 →</span></RouterLink><RouterLink :to="`/projects/${id}/reports`">报告中心 <span>开发与风险报告 →</span></RouterLink><RouterLink :to="`/projects/${id}/knowledge`">知识库 <span>项目资料与学习内容 →</span></RouterLink></div>
        <n-alert v-if="project.status !== 'active'" type="warning" title="项目尚未完成初始化">暂不能使用文件与助手功能。初始化失败时可返回项目列表，使用同名项目重新创建以重试初始化。</n-alert>
        <template v-else>
          <ProjectFileUploadCard :project-id="id" :disabled="filesBusy" @busy="syncBusy = $event" @changed="fileRevision++" />
          <ProjectFileList :project-id="id" :revision="fileRevision" :disabled="syncBusy" @busy="filesBusy = $event" />
        </template>
      </template>
    </n-spin>
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDialog, useMessage } from 'naive-ui'
import { deleteProject, getProjectDetail } from '../api'
import type { ProjectDetail } from '../types'
import { useProjectStore } from '../store'
import ProjectFileUploadCard from '../components/project-file-upload-card.vue'
import ProjectFileList from '../components/project-file-list.vue'
import ProjectStatus from '@/shared/components/project-status.vue'
import RequestError from '@/shared/components/request-error.vue'
import { errorMessage, formatDate } from '@/shared/utils/format'
const id = String(useRoute().params.id); const router = useRouter(); const store = useProjectStore(); const dialog = useDialog(); const message = useMessage()
const project = ref<ProjectDetail | null>(null); const error = ref(''); const loading = ref(false); const fileRevision = ref(0); const syncBusy = ref(false); const filesBusy = ref(false)
async function load() { loading.value = true; error.value = ''; try { project.value = await getProjectDetail(id); store.currentProjectId = id } catch(e) { error.value = errorMessage(e) } finally { loading.value = false } }
onMounted(load)
function remove() {
  if (syncBusy.value || filesBusy.value) { message.warning('请等待当前文件操作完成'); return }
  dialog.warning({ title: '删除项目', content: '项目将从工作台移除，文件及历史内容将在保留期后清理。确认删除此项目？', positiveText: '删除项目', negativeText: '取消',
    onPositiveClick: async () => { try { await deleteProject(id); await store.loadProjects(); await router.push('/projects') } catch(e) { error.value = errorMessage(e); return false } },
  })
}
</script>
<style scoped>
.project-links { display:grid;grid-template-columns:repeat(3,1fr);margin:28px 0;padding:24px;gap:24px; }
.project-links a { display:grid;gap:10px;text-decoration:none;color:var(--pm-text);font-size:17px;font-weight:600; }
.project-links span { font-size:13px;color:var(--pm-blue-dark);font-weight:400; }
:deep(.upload-card) { margin-bottom:24px; }
</style>
