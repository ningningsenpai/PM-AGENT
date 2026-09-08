import type { RouteRecordRaw } from 'vue-router'
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import MainLayout from '@/layouts/MainLayout.vue'
const feature = () => import('@/shared/components/feature-state.vue')
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'intro',
    component: () => import('@/modules/landing/pages/ProjectIntroPage.vue'),
    meta: { public: true },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/modules/auth/pages/LoginPage.vue'),
    meta: { public: true, guestOnly: true },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/modules/auth/pages/RegisterPage.vue'),
    meta: { public: true, guestOnly: true },
  },
  {
    path: '/',
    component: MainLayout,
    children: [
      {
        path: 'overview',
        component: () => import('@/modules/workspace/pages/overview-page.vue'),
        meta: { section: 'overview' },
      },
      {
        path: 'profile',
        name: 'profile',
        component: () => import('@/modules/auth/pages/UserProfilePage.vue'),
        meta: { title: '个人资料' },
      },
      {
        path: 'projects',
        name: 'projects',
        component: () => import('@/modules/project/pages/ProjectListPage.vue'),
        meta: { section: 'projects' },
      },
      {
        path: 'projects/:id',
        name: 'project-detail',
        component: () =>
          import('@/modules/project/pages/ProjectDetailPage.vue'),
        meta: { section: 'projects' },
      },
      {
        path: 'projects/:id/tasks',
        name: 'task-board',
        component: () => import('@/modules/task/pages/TaskBoardPage.vue'),
        meta: { section: 'tasks' },
      },
      {
        path: 'projects/:id/assistant',
        component: () => import('@/modules/assistant/pages/assistant-page.vue'),
        meta: { section: 'assistant' },
      },
      {
        path: 'projects/:id/reports',
        component: () => import('@/modules/report/pages/report-page.vue'),
        meta: { section: 'reports' },
      },
      {
        path: 'projects/:id/knowledge',
        component: () => import('@/modules/workspace/pages/knowledge-page.vue'),
        meta: { section: 'knowledge' },
      },
      ...[{ key: 'risk', title: '风险中心' }].map((item) => ({
        path: 'projects/:id/' + item.key,
        component: feature,
        meta: { section: item.key, title: item.title },
      })),
      ...[
        { key: 'assistant', title: 'PM 助手' },
        { key: 'reports', title: '报告中心' },
        { key: 'knowledge', title: '知识库' },
        { key: 'risk', title: '风险中心' },
        { key: 'tasks', title: '任务看板' },
      ].map((item) => ({
        path: 'workspace/' + item.key,
        component: feature,
        meta: { section: item.key, title: item.title },
      })),
      {
        path: 'settings',
        component: feature,
        meta: { section: 'settings', title: '系统设置' },
      },
      {
        path: ':pathMatch(.*)*',
        component: feature,
        meta: { title: '页面不存在' },
      },
    ],
  },
]
export const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.public)
    return to.meta.guestOnly && auth.token ? { name: 'projects' } : true
  if (!auth.token) return { name: 'login', query: { redirect: to.fullPath } }
  if (!auth.user) {
    try {
      await auth.loadCurrentUser()
    } catch {
      if (!auth.token)
        return { name: 'login', query: { redirect: to.fullPath } }
    }
  }
  return true
})
