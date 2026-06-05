<template>
  <div class="login-page">
    <section class="login-hero">
      <div class="hero-mark">PM</div>
      <p class="page-eyebrow">PM-Agent</p>
      <h1>把项目状态变成<br />可追踪的执行线索</h1>
      <p class="hero-copy">
        第 1 阶段先跑通登录、项目、任务和看板闭环，让后续 Agent 有真实业务数据可以分析。
      </p>
      <div class="hero-stack">
        <span>项目</span>
        <span>任务</span>
        <span>看板</span>
        <span>Trace</span>
      </div>
    </section>

    <n-card class="login-card glass-card" :bordered="false">
      <h2>登录工作台</h2>
      <p>使用本地演示用户进入第 1 阶段 MVP。</p>
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
        <n-form-item label="用户名" path="username">
          <n-input v-model:value="form.username" placeholder="admin" size="large" />
        </n-form-item>
        <n-form-item label="密码" path="password">
          <n-input v-model:value="form.password" type="password" placeholder="任意非空密码" size="large" show-password-on="click" />
        </n-form-item>
        <n-button type="primary" size="large" block :loading="loading" @click="handleLogin">
          进入项目工作台
        </n-button>
      </n-form>
      <div class="login-tip">Mock 模式下用户名默认 admin，密码任意非空。</div>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage, type FormInst, type FormRules } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const message = useMessage()
const authStore = useAuthStore()
const formRef = ref<FormInst | null>(null)
const loading = ref(false)

const form = reactive({
  username: 'admin',
  password: 'password',
})

const rules: FormRules = {
  username: { required: true, message: '请输入用户名', trigger: 'blur' },
  password: { required: true, message: '请输入密码', trigger: 'blur' },
}

async function handleLogin() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await authStore.login(form)
    message.success('登录成功')
    await router.push((route.query.redirect as string) || '/projects')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: grid;
  min-height: 100vh;
  grid-template-columns: 1.2fr 440px;
  gap: 48px;
  align-items: center;
  padding: 64px 8vw;
}

.login-hero h1 {
  max-width: 780px;
  margin: 0;
  color: #0f172a;
  font-size: 64px;
  line-height: 1.04;
  letter-spacing: -0.07em;
}

.hero-mark {
  display: inline-flex;
  width: 72px;
  height: 72px;
  align-items: center;
  justify-content: center;
  margin-bottom: 32px;
  border-radius: 24px;
  background: #0f172a;
  color: white;
  font-weight: 900;
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.28);
}

.hero-copy {
  max-width: 560px;
  margin: 24px 0 0;
  color: #64748b;
  font-size: 17px;
  line-height: 1.8;
}

.hero-stack {
  display: flex;
  gap: 10px;
  margin-top: 36px;
}

.hero-stack span {
  padding: 8px 14px;
  border: 1px solid rgba(37, 99, 235, 0.16);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: #2563eb;
  font-size: 13px;
}

.login-card {
  padding: 18px;
}

.login-card h2 {
  margin: 0 0 8px;
  font-size: 28px;
  letter-spacing: -0.04em;
}

.login-card p {
  margin: 0 0 28px;
  color: #64748b;
}

.login-tip {
  margin-top: 18px;
  color: #94a3b8;
  font-size: 13px;
}
</style>
