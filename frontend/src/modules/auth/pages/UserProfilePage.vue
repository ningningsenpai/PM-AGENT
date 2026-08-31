<template>
  <div class="page-shell">
    <div class="page-title-row">
      <div>
        <p class="page-eyebrow">Profile</p>
        <h1 class="page-title">个人资料</h1>
        <p class="page-description">查看当前登录用户信息，并修改用户名和登录邮箱。</p>
      </div>
      <n-button :loading="refreshing" @click="handleRefresh">刷新资料</n-button>
    </div>

    <div class="profile-grid">
      <n-card class="glass-card profile-summary" :bordered="false">
        <div class="avatar">{{ avatarText }}</div>
        <h2>{{ authStore.user?.username || '未命名用户' }}</h2>
        <p>{{ authStore.user?.email || '暂无邮箱' }}</p>
        <n-tag :type="authStore.user?.status === 'enabled' ? 'success' : 'warning'" round>
          {{ authStore.user?.status === 'enabled' ? '账号正常' : '账号不可用' }}
        </n-tag>

        <n-descriptions class="profile-details" label-placement="left" :column="1">
          <n-descriptions-item label="用户 ID">{{ authStore.user?.id ?? '-' }}</n-descriptions-item>
          <n-descriptions-item label="最近登录">
            {{ formatDate(authStore.user?.lastLoginAt) }}
          </n-descriptions-item>
        </n-descriptions>
      </n-card>

      <n-card class="glass-card profile-form-card" :bordered="false" title="修改基础信息">
        <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" size="large">
          <n-form-item label="用户名" path="username">
            <n-input v-model:value="form.username" placeholder="请输入用户名" clearable />
          </n-form-item>
          <n-form-item label="登录邮箱" path="email">
            <n-input v-model:value="form.email" placeholder="name@example.com" clearable />
          </n-form-item>
          <n-button type="primary" :loading="saving" @click="handleSave">保存修改</n-button>
        </n-form>
      </n-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useMessage, type FormInst, type FormRules } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const message = useMessage()
const formRef = ref<FormInst | null>(null)
const refreshing = ref(false)
const saving = ref(false)
const form = reactive({
  username: '',
  email: '',
})

const avatarText = computed(() => authStore.user?.username.trim().slice(0, 1).toUpperCase() || 'U')

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { max: 64, message: '用户名不能超过 64 个字符', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    {
      trigger: 'blur',
      validator: (_rule, value: string) =>
        /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) || new Error('请输入正确的邮箱地址'),
    },
  ],
}

watch(
  () => authStore.user,
  (user) => {
    if (!user) return
    form.username = user.username
    form.email = user.email
  },
  { immediate: true },
)

async function handleRefresh() {
  refreshing.value = true
  try {
    await authStore.loadCurrentUser()
    message.success('用户资料已刷新')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '用户资料刷新失败')
  } finally {
    refreshing.value = false
  }
}

async function handleSave() {
  await formRef.value?.validate()
  saving.value = true
  try {
    await authStore.updateCurrentUser({
      username: form.username.trim(),
      email: form.email.trim(),
    })
    message.success('用户资料修改成功')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '用户资料修改失败')
  } finally {
    saving.value = false
  }
}

function formatDate(value?: string | null) {
  if (!value) return '暂无记录'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.profile-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.8fr) minmax(420px, 1.4fr);
  gap: 20px;
}

.profile-summary {
  text-align: center;
}

.avatar {
  display: inline-flex;
  width: 72px;
  height: 72px;
  align-items: center;
  justify-content: center;
  border-radius: 24px;
  background: var(--pm-text);
  color: white;
  font-size: 28px;
  font-weight: 800;
}

.profile-summary h2 {
  margin: 18px 0 6px;
  color: var(--pm-text);
}

.profile-summary > p {
  margin: 0 0 16px;
  color: var(--pm-text-secondary);
}

.profile-details {
  margin-top: 28px;
  text-align: left;
}

.profile-form-card {
  min-height: 360px;
}
</style>
