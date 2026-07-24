<template>
  <div class="auth-page">
    <div class="auth-glow auth-glow-blue"></div>
    <div class="auth-glow auth-glow-green"></div>
    <div class="auth-glow auth-glow-yellow"></div>

    <AuthBrandHero />

    <AuthPanel title="登录工作台" description="使用项目账号进入 PM-Agent，继续推进项目、任务和风险线索。">
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" size="large">
        <n-form-item label="邮箱" path="email">
          <n-input v-model:value="form.email" placeholder="admin@pm-agent.local" clearable />
        </n-form-item>
        <n-form-item label="密码" path="password">
          <n-input v-model:value="form.password" type="password" placeholder="请输入密码" show-password-on="click" />
        </n-form-item>

        <div class="form-row">
          <n-checkbox v-model:checked="form.remember">记住登录</n-checkbox>
          <RouterLink class="muted-link" to="/">忘记密码</RouterLink>
        </div>

        <n-button type="primary" size="large" block :loading="loading" @click="handleLogin">
          进入项目工作台
        </n-button>
      </n-form>

      <template #footer>
        <div class="auth-footer">
          <span>还没有账号？</span>
          <RouterLink to="/register">注册账号</RouterLink>
          <RouterLink class="intro-link" to="/">返回项目介绍</RouterLink>
        </div>
      </template>
    </AuthPanel>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useMessage, type FormInst, type FormRules } from 'naive-ui'
import AuthBrandHero from '@/modules/auth/components/AuthBrandHero.vue'
import AuthPanel from '@/modules/auth/components/AuthPanel.vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const message = useMessage()
const authStore = useAuthStore()
const formRef = ref<FormInst | null>(null)
const loading = ref(false)

const form = reactive({
  email: '',
  password: '',
  remember: true,
})

const rules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    {
      trigger: 'blur',
      validator: (_rule, value: string) =>
        /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) || new Error('请输入正确的邮箱地址'),
    },
  ],
  password: { required: true, message: '请输入密码', trigger: 'blur' },
}

async function handleLogin() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await authStore.login({ email: form.email, password: form.password })
    message.success('登录成功')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/projects'
    await router.push(redirect)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '登录失败，请检查邮箱和密码')
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
  padding: 64px 8vw;
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

.form-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: -4px 0 26px;
}

.muted-link,
.auth-footer a {
  color: var(--pm-blue-dark);
  font-size: 13px;
  font-weight: 650;
  text-decoration: none;
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

.auth-footer .intro-link {
  width: 100%;
  color: var(--pm-text-muted);
  text-align: center;
}
</style>
