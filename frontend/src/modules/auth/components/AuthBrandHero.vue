<template>
  <section class="auth-brand-hero">
    <RouterLink class="brand-row" to="/">
      <span class="brand-mark">
        <span class="orbit orbit-blue"></span>
        <span class="orbit orbit-green"></span>
        <span class="orbit orbit-yellow"></span>
        <span class="trace-line"></span>
        <strong>PM</strong>
      </span>
      <span>
        <strong>PM-Agent</strong>
        <small>项目执行工作台</small>
      </span>
    </RouterLink>

    <p class="page-eyebrow">{{ eyebrow }}</p>
    <h1>{{ title }}</h1>
    <p class="hero-copy">{{ description }}</p>

    <div class="execution-path" aria-label="PM-Agent 执行线索路径">
      <span v-for="item in pathItems" :key="item" class="path-item">
        <i></i>
        {{ item }}
      </span>
    </div>

    <div class="insight-card glass-card">
      <span class="insight-dot"></span>
      <div>
        <strong>Agent 洞察预留</strong>
        <p>后续可基于项目、任务、风险与 Trace 数据生成分析建议。</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'

withDefaults(
  defineProps<{
    eyebrow?: string
    title?: string
    description?: string
    pathItems?: string[]
  }>(),
  {
    eyebrow: 'PM-Agent',
    title: '把项目状态变成可追踪的执行线索',
    description: '围绕项目、需求、任务、风险和报告形成可落地的管理闭环，让 Agent 后续分析有真实业务数据可依赖。',
    pathItems: () => ['项目', '任务', '状态', 'Trace', 'Agent'],
  },
)
</script>

<style scoped>
.auth-brand-hero {
  position: relative;
  z-index: 1;
}

.brand-row {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 64px;
  color: var(--pm-text);
  text-decoration: none;
}

.brand-row strong,
.brand-row small {
  display: block;
}

.brand-row > span:last-child strong {
  font-size: 20px;
  font-weight: 800;
}

.brand-row small {
  margin-top: 3px;
  color: var(--pm-text-secondary);
  font-size: 12px;
}

.brand-mark {
  position: relative;
  display: inline-flex;
  width: 48px;
  height: 48px;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 16px;
  background: var(--pm-text);
  box-shadow: 0 22px 50px rgba(19, 32, 51, 0.22);
}

.brand-mark strong {
  position: relative;
  z-index: 2;
  color: #ffffff;
  font-size: 13px;
  font-weight: 900;
  letter-spacing: -0.04em;
}

.orbit,
.trace-line {
  position: absolute;
  display: block;
}

.orbit-blue {
  top: 8px;
  left: 8px;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: var(--pm-blue);
}

.orbit-green {
  right: 8px;
  bottom: 8px;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: var(--pm-green);
}

.orbit-yellow {
  top: 9px;
  right: 8px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--pm-yellow);
}

.trace-line {
  top: 19px;
  left: 18px;
  z-index: 1;
  width: 18px;
  height: 2px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
}

.auth-brand-hero h1 {
  max-width: 720px;
  margin: 0;
  color: var(--pm-text);
  font-size: 64px;
  font-weight: 850;
  line-height: 1.06;
  letter-spacing: -0.075em;
  white-space: pre-line;
}

.hero-copy {
  max-width: 560px;
  margin: 28px 0 0;
  color: var(--pm-text-secondary);
  font-size: 17px;
  line-height: 1.85;
}

.execution-path {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 42px;
}

.path-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px;
  border: 1px solid rgba(47, 125, 246, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--pm-blue-dark);
  font-size: 13px;
  font-weight: 650;
}

.path-item i {
  display: inline-flex;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: currentColor;
}

.insight-card {
  display: flex;
  max-width: 430px;
  gap: 16px;
  margin-top: 72px;
  padding: 22px;
  border-radius: 24px;
}

.insight-dot {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: var(--pm-yellow);
  box-shadow: 0 12px 28px rgba(245, 184, 61, 0.26);
}

.insight-card strong {
  color: var(--pm-text);
  font-size: 16px;
}

.insight-card p {
  margin: 8px 0 0;
  color: var(--pm-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}
</style>
