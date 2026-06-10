<template>
  <div class="auth-page">
    <div class="auth-glow auth-glow-blue"></div>
    <div class="auth-glow auth-glow-green"></div>
    <div class="auth-glow auth-glow-yellow"></div>

    <AuthBrandHero
      title="创建账号，开始沉淀项目执行线索"
      description="注册后即可进入项目工作台，先完成项目、任务和看板闭环，后续逐步接入 Agent 分析能力。"
    />

    <AuthPanel title="注册账号" description="填写基础账号信息，注册成功后会自动进入项目工作台。">
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" size="large">
        <n-form-item label="显示名称" path="displayName">
          <n-input v-model:value="form.displayName" placeholder="例如：宁宁" clearable />
        </n-form-item>
        <n-form-item label="用户名" path="username">
          <n-input v-model:value="form.username" placeholder="用于登录，例如：ning" clearable />
        </n-form-item>
        <n-form-item label="邮箱（可选）" path="email">
          <n-input v-model:value="form.email" placeholder="admin@pm-agent.local" clearable />
        </n-form-item>
        <n-form-item label="手机号（可选）" path="mobile">
          <n-input v-model:value="form.mobile" placeholder="13800000000" clearable />
        </n-form-item>
        <n-form-item label="密码" path="password">
          <n-input v-model:value="form.password" type="password" placeholder="请输入 8 到 64 位密码" show-password-on="click" />
        </n-form-item>
        <n-form-item label="确认密码" path="confirmPassword">
          <n-input v-model:value="form.confirmPassword" type="password" placeholder="请再次输入密码" show-password-on="click" />
        </n-form-item>

        <n-button type="primary" size="large" block :loading="loading" @click="handleRegister">
          创建账号并进入工作台
        </n-button>
      </n-form>

      <template #footer>
        <div class="auth-footer">
          <span>已有账号？</span>
          <RouterLink to="/login">返回登录</RouterLink>
          <RouterLink class="intro-link" to="/">查看项目介绍</RouterLink>
        </div>
      </template>
    </AuthPanel>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useMessage, type FormInst, type FormRules } from 'naive-ui'
import AuthBrandHero from '@/modules/auth/components/AuthBrandHero.vue'
import AuthPanel from '@/modules/auth/components/AuthPanel.vue'
import { useAuthStore } from '@/stores/auth'

interface RegisterForm {
  displayName: string
  username: string
  email: string
  mobile: string
  password: string
  confirmPassword: string
}

const router = useRouter()
const message = useMessage()
const authStore = useAuthStore()
const formRef = ref<FormInst | null>(null)
const loading = ref(false)

const form = reactive<RegisterForm>({
  displayName: '',
  username: '',
  email: '',
  mobile: '',
  password: '',
  confirmPassword: '',
})

const rules: FormRules = {
  displayName: { required: true, message: '请输入显示名称', trigger: 'blur' },
  username: { required: true, message: '请输入用户名', trigger: 'blur' },
  email: {
    trigger: 'blur',
    validator: (_rule, value: string) => {
      if (!value) return true
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) || new Error('请输入正确的邮箱地址')
    },
  },
  mobile: {
    trigger: 'blur',
    validator: (_rule, value: string) => {
      if (!value) return true
      return /^1\d{10}$/.test(value) || new Error('请输入正确的手机号')
    },
  },
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    {
      trigger: 'blur',
      validator: (_rule, value: string) => {
        if (!value) return true
        return (value.length >= 8 && value.length <= 64) || new Error('密码长度需为 8 到 64 位')
      },
    },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      trigger: ['blur', 'input'],
      validator: (_rule, value: string) => value === form.password || new Error('两次输入的密码不一致'),
    },
  ],
}

async function handleRegister() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await authStore.register({
      username: form.username,
      password: form.password,
      displayName: form.displayName,
      email: form.email || undefined,
      mobile: form.mobile || undefined,
    })
    message.success('注册成功')
    await router.push('/projects')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '注册失败，请稍后重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  position: relative;
  display: grid;
  min-height: 100vh;
  grid-template-columns: minmax(640px, 1fr) 448px;
  gap: 72px;
  align-items: center;
  overflow: hidden;
  padding: 48px 8vw;
}

.auth-glow {
  position: fixed;
  z-index: 0;
  border-radius: 999px;
  filter: blur(6px);
  pointer-events: none;
}

.auth-glow-blue {
  top: -140px;
  left: -130px;
  width: 480px;
  height: 480px;
  background: rgba(47, 125, 246, 0.12);
}

.auth-glow-green {
  top: -120px;
  right: -90px;
  width: 520px;
  height: 420px;
  background: rgba(38, 185, 131, 0.1);
}

.auth-glow-yellow {
  right: 4vw;
  bottom: -120px;
  width: 420px;
  height: 280px;
  background: rgba(245, 184, 61, 0.12);
}

.auth-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: center;
  color: var(--pm-text-secondary);
  font-size: 13px;
}

.auth-footer a {
  color: var(--pm-blue-dark);
  font-weight: 650;
  text-decoration: none;
}

.auth-footer .intro-link {
  width: 100%;
  color: var(--pm-text-muted);
  text-align: center;
}
</style>
