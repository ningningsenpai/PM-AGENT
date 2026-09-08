<template>
  <div class="workspace">
    <aside class="workspace-sidebar">
      <RouterLink class="workspace-brand" to="/overview"><BrandMark /><span><strong>PM-Agent</strong><small>项目工作台</small></span></RouterLink>
      <nav aria-label="主导航">
        <RouterLink v-for="item in navigation" :key="item.key" :to="item.to" :class="['nav-item', { active: route.meta.section === item.key }]">
          <img :src="route.meta.section === item.key ? activeDot : idleDot" alt="" width="12" height="12" />{{ item.label }}
        </RouterLink>
      </nav>
      <div class="sidebar-foot"><span class="status-dot" style="background:var(--pm-green)" />个人项目空间<p>从资料出发，让每个结论有据可查。</p></div>
    </aside>
    <div class="workspace-body">
      <header class="workspace-header">
        <div class="project-switch"><span class="muted">当前项目</span><n-select :value="projectId || null" :options="projectOptions" :loading="projects.loading" placeholder="选择项目" filterable @update:value="switchProject" /></div>
        <div class="header-account"><n-tag v-if="useMock" type="warning" size="small">演示数据</n-tag>
          <n-dropdown :options="userOptions" @select="userAction"><button class="account-button"><span class="user-avatar">{{ auth.user?.username.slice(0, 1) || '用' }}</span><span><b>{{ auth.user?.username }}</b><small>个人项目</small></span></button></n-dropdown>
        </div>
      </header>
      <main class="workspace-content">
        <RouterView :key="String(route.params.id || '') + ':' + String(auth.user?.id || '')" />
      </main>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDialog, useMessage } from 'naive-ui'
import { useProjectStore } from '@/modules/project/store'
import { useAuthStore } from '@/stores/auth'
import { useMock } from '@/mock'
import BrandMark from '@/shared/components/brand-mark.vue'
import idleDot from '@/assets/figma/nav-idle.svg'
import activeDot from '@/assets/figma/nav-active.svg'
const route = useRoute(); const router = useRouter(); const projects = useProjectStore(); const auth = useAuthStore()
const dialog = useDialog(); const message = useMessage()
const projectId = computed(() => typeof route.params.id === 'string' ? route.params.id : projects.currentProjectId)
const projectOptions = computed(() => projects.projects.map(p => ({ label: p.projectName, value: p.id })))
const navigation = computed(() => [
  { key: 'overview', label: '个人工作台', to: '/overview' },
  { key: 'projects', label: '项目管理', to: '/projects' },
  ...[{ key: 'tasks', label: '任务看板' }, { key: 'risk', label: '风险中心' }, { key: 'assistant', label: 'PM 助手' }, { key: 'knowledge', label: '知识库' }, { key: 'reports', label: '报告中心' }].map(item => ({ ...item, to: projectId.value ? `/projects/${projectId.value}/${item.key}` : `/workspace/${item.key}` })),
  { key: 'settings', label: '系统设置', to: '/settings' },
])
const userOptions = [{ label: '个人资料', key: 'profile' }, { label: '账号安全', key: 'security' }, { type: 'divider', key: 'divider' }, { label: '退出登录', key: 'logout' }]
onMounted(() => { if (!projects.projects.length) void projects.loadProjects() })
function switchProject(id: string) {
  projects.currentProjectId = id
  if (route.params.id || route.path.startsWith('/workspace/')) {
    const section = String(route.meta.section || 'projects')
    void router.push(section === 'projects' ? `/projects/${id}` : `/projects/${id}/${section}`)
  }
}
function userAction(key: string) {
  if (key !== 'logout') { void router.push('/profile' + (key === 'security' ? '?tab=security' : '')); return }
  dialog.warning({ title: '退出登录', content: '确认退出当前账号？', positiveText: '退出登录', negativeText: '取消', onPositiveClick: async () => {
    try { await auth.logout() } catch { message.warning('本地登录态已清除，服务端注销未确认') }
    projects.$reset(); await router.replace('/login')
  } })
}
</script>
