import type { RouteRecordRaw } from 'vue-router'
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginPage from '@/modules/auth/pages/LoginPage.vue'
import RegisterPage from '@/modules/auth/pages/RegisterPage.vue'
import ProjectIntroPage from '@/modules/landing/pages/ProjectIntroPage.vue'
import MainLayout from '@/layouts/MainLayout.vue'
import ProjectListPage from '@/modules/project/pages/ProjectListPage.vue'
import ProjectDetailPage from '@/modules/project/pages/ProjectDetailPage.vue'
import TaskBoardPage from '@/modules/task/pages/TaskBoardPage.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'intro',
    component: ProjectIntroPage,
    meta: { public: true },
  },
  {
    path: '/login',
    name: 'login',
    component: LoginPage,
    meta: { public: true, guestOnly: true },
  },
  {
    path: '/register',
    name: 'register',
    component: RegisterPage,
    meta: { public: true, guestOnly: true },
  },
  {
    path: '/projects',
    component: MainLayout,
    children: [
      {
        path: '',
        name: 'projects',
        component: ProjectListPage,
      },
      {
        path: ':id',
        name: 'project-detail',
        component: ProjectDetailPage,
      },
      {
        path: ':id/tasks',
        name: 'task-board',
        component: TaskBoardPage,
      },
    ],
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()

  if (to.meta.public) {
    if (to.meta.guestOnly && authStore.token) {
      return { name: 'projects' }
    }
    return true
  }

  if (!authStore.token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (!authStore.user) {
    try {
      await authStore.loadCurrentUser()
    } catch {
      authStore.clearAuth()
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }

  return true
})
