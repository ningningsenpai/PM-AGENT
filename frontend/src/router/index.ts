import type { RouteRecordRaw } from 'vue-router'
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginPage from '@/modules/auth/pages/LoginPage.vue'
import MainLayout from '@/layouts/MainLayout.vue'
import ProjectListPage from '@/modules/project/pages/ProjectListPage.vue'
import ProjectDetailPage from '@/modules/project/pages/ProjectDetailPage.vue'
import TaskBoardPage from '@/modules/task/pages/TaskBoardPage.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: LoginPage,
    meta: { public: true },
  },
  {
    path: '/',
    component: MainLayout,
    redirect: '/projects',
    children: [
      {
        path: 'projects',
        name: 'projects',
        component: ProjectListPage,
      },
      {
        path: 'projects/:id',
        name: 'project-detail',
        component: ProjectDetailPage,
      },
      {
        path: 'projects/:id/tasks',
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

router.beforeEach((to) => {
  const authStore = useAuthStore()

  if (to.meta.public) {
    return true
  }

  if (!authStore.token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  return true
})
