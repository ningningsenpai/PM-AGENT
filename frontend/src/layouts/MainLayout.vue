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
          <n-tag :type="useMock ? 'success' : 'info'" round>{{ useMock ? 'Mock 数据' : '真实接口' }}</n-tag>
          <span>{{ authStore.user?.displayName || '未命名用户' }}</span>
          <n-button quaternary size="small" :loading="logoutLoading" @click="handleLogout">退出</n-button>
        </div>
      </n-layout-header>

      <n-layout-content class="layout-content">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useMessage, type MenuOption } from 'naive-ui'
import { useMock } from '@/mock'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const authStore = useAuthStore()
const logoutLoading = ref(false)

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

async function handleLogout() {
  logoutLoading.value = true
  try {
    await authStore.logout()
    message.success('已退出登录')
    await router.push('/login')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '退出登录失败')
  } finally {
    logoutLoading.value = false
  }
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
  background: var(--pm-text);
  color: white;
  font-weight: 900;
}

.brand strong,
.brand span {
  display: block;
}

.brand span {
  margin-top: 2px;
  color: var(--pm-text-secondary);
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
  color: var(--pm-text-secondary);
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
