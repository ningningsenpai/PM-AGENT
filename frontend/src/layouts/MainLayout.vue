<template>
  <n-layout class="main-layout" has-sider>
    <n-layout-sider class="layout-sider" :width="256" bordered>
      <div class="brand">
        <div class="brand-logo">PM</div>
        <div>
          <strong>PM-Agent</strong>
          <span>智能项目管理</span>
        </div>
      </div>
      <n-menu :value="activeKey" :options="menuOptions" @update:value="handleMenu" />
    </n-layout-sider>

    <n-layout>
      <n-layout-header class="layout-header" bordered>
        <div>
          <span class="header-label">第 1 阶段</span>
          <strong>项目基础骨架</strong>
        </div>
        <div class="header-user">
          <n-tag type="success" round>Mock 数据</n-tag>
          <span>{{ authStore.user?.displayName || '宁宁' }}</span>
          <n-button quaternary size="small" @click="logout">退出</n-button>
        </div>
      </n-layout-header>

      <n-layout-content class="layout-content">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup lang="ts">
import { computed, h } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import type { MenuOption } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const activeKey = computed(() => (route.path.startsWith('/projects') ? 'projects' : 'projects'))

const menuOptions: MenuOption[] = [
  {
    label: () => h(RouterLink, { to: '/projects' }, { default: () => '项目工作台' }),
    key: 'projects',
  },
]

function handleMenu() {
  return undefined
}

async function logout() {
  authStore.logout()
  await router.push('/login')
}
</script>

<style scoped>
.main-layout {
  min-height: 100vh;
  background: transparent;
}

.layout-sider {
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(18px);
}

.brand {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 24px 20px;
}

.brand-logo {
  display: inline-flex;
  width: 42px;
  height: 42px;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: #0f172a;
  color: white;
  font-weight: 900;
}

.brand strong,
.brand span {
  display: block;
}

.brand span {
  margin-top: 2px;
  color: #64748b;
  font-size: 12px;
}

.layout-header {
  display: flex;
  height: 68px;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(18px);
}

.header-label {
  margin-right: 10px;
  color: #64748b;
  font-size: 13px;
}

.header-user {
  display: flex;
  gap: 12px;
  align-items: center;
}

.layout-content {
  padding: 28px;
}
</style>
