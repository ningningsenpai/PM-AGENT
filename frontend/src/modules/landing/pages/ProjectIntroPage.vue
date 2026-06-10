<template>
  <main class="intro-page">
    <div class="intro-glow intro-glow-blue"></div>
    <div class="intro-glow intro-glow-green"></div>
    <div class="intro-glow intro-glow-yellow"></div>

    <header class="intro-header">
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
          <small>智能项目管理 Agent 平台</small>
        </span>
      </RouterLink>

      <nav>
        <a href="#capability">项目能力</a>
        <a href="#preview">工作台预览</a>
        <a href="#agent">Agent 洞察</a>
      </nav>

      <div class="header-actions">
        <RouterLink class="ghost-link" to="/login">登录</RouterLink>
        <RouterLink class="primary-link" to="/register">注册账号</RouterLink>
      </div>
    </header>

    <section class="hero-section">
      <div class="hero-copy">
        <span class="stage-pill">第 1 阶段 · 项目基础骨架</span>
        <h1>把项目状态变成可追踪的执行线索</h1>
        <p>
          PM-Agent 先围绕项目、任务、风险和报告建立真实业务闭环，再让 Agent 基于 Trace 数据进行分析、拆解和总结。
        </p>
        <div class="hero-actions">
          <RouterLink class="primary-cta" :to="primaryEntry">进入工作台</RouterLink>
          <RouterLink class="secondary-cta" to="/register">创建账号</RouterLink>
        </div>
      </div>

      <section id="preview" class="workspace-preview glass-card">
        <div class="preview-topbar">
          <span class="mini-brand">PM</span>
          <strong>项目工作台</strong>
          <span class="health-pill">执行温度 正常</span>
        </div>
        <div class="metric-grid">
          <div v-for="metric in metrics" :key="metric.name" class="metric-card">
            <span :class="['metric-strip', metric.color]"></span>
            <small>{{ metric.name }}</small>
            <strong>{{ metric.value }}</strong>
          </div>
        </div>
        <div class="preview-content">
          <div class="project-card">
            <span class="project-strip"></span>
            <h3>PM-Agent 平台 MVP</h3>
            <p>认证、项目与任务看板形成第一条闭环。</p>
            <div class="progress-track"><span></span></div>
            <b>72%</b>
          </div>
          <div id="agent" class="insight-card">
            <span></span>
            <h3>Agent 洞察</h3>
            <p>建议优先补齐项目与任务接口联调。</p>
          </div>
        </div>
      </section>
    </section>

    <section id="capability" class="capability-section">
      <div class="section-heading">
        <p class="page-eyebrow">CAPABILITY</p>
        <h2>从业务闭环开始，而不是只做一个聊天窗口</h2>
        <p>第一版先让项目、需求、任务、风险和报告有结构化数据，后续 Agent 才能给出可信建议。</p>
      </div>

      <div class="value-grid">
        <article v-for="item in values" :key="item.title" class="value-card glass-card">
          <span :class="['value-icon', item.color]"></span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.description }}</p>
        </article>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const primaryEntry = computed(() => (authStore.token ? '/projects' : '/login'))

const metrics = [
  { name: '进行中项目', value: '12', color: 'blue' },
  { name: '本周完成', value: '38', color: 'green' },
  { name: '风险线索', value: '6', color: 'yellow' },
]

const values = [
  { title: '项目全局视图', description: '聚合项目状态、进度、成员和近期动态，减少信息分散。', color: 'blue' },
  { title: '任务状态流转', description: '以看板方式展示待处理、进行中、阻塞和已完成任务。', color: 'green' },
  { title: '风险线索提示', description: '将延期、阻塞和不确定因素沉淀为可处理的风险线索。', color: 'yellow' },
  { title: 'Agent 洞察', description: '后续基于业务数据生成风险分析、需求拆解和周报草稿。', color: 'yellow' },
  { title: 'Trace 可追溯', description: '记录 Agent 分析输入、工具调用和输出结论，便于复盘。', color: 'blue' },
]
</script>

<style scoped>
.intro-page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  padding: 38px 72px 84px;
}

.intro-glow {
  position: fixed;
  z-index: 0;
  border-radius: 999px;
  pointer-events: none;
}

.intro-glow-blue {
  top: -120px;
  left: -120px;
  width: 470px;
  height: 470px;
  background: rgba(47, 125, 246, 0.12);
}

.intro-glow-green {
  top: -130px;
  right: -40px;
  width: 500px;
  height: 430px;
  background: rgba(38, 185, 131, 0.1);
}

.intro-glow-yellow {
  right: 20px;
  bottom: -90px;
  width: 420px;
  height: 280px;
  background: rgba(245, 184, 61, 0.12);
}

.intro-header,
.hero-section,
.capability-section {
  position: relative;
  z-index: 1;
}

.intro-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
}

.brand-row {
  display: inline-flex;
  align-items: center;
  gap: 14px;
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

.brand-mark,
.mini-brand {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: var(--pm-text);
  color: #ffffff;
  font-weight: 900;
}

.brand-mark {
  width: 46px;
  height: 46px;
  border-radius: 16px;
  box-shadow: 0 22px 50px rgba(19, 32, 51, 0.22);
}

.brand-mark strong {
  position: relative;
  z-index: 2;
  font-size: 13px;
}

.orbit,
.trace-line {
  position: absolute;
}

.orbit-blue {
  top: 8px;
  left: 8px;
  width: 21px;
  height: 21px;
  border-radius: 999px;
  background: var(--pm-blue);
}

.orbit-green {
  right: 8px;
  bottom: 8px;
  width: 21px;
  height: 21px;
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

nav {
  display: flex;
  gap: 32px;
}

nav a,
.ghost-link,
.primary-link,
.primary-cta,
.secondary-cta {
  font-size: 14px;
  font-weight: 650;
  text-decoration: none;
}

nav a,
.ghost-link,
.secondary-cta {
  color: var(--pm-text-secondary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

.primary-link,
.primary-cta {
  border-radius: 14px;
  background: var(--pm-blue);
  color: #ffffff;
  box-shadow: 0 16px 34px rgba(47, 125, 246, 0.18);
}

.primary-link {
  padding: 11px 20px;
}

.hero-section {
  display: grid;
  grid-template-columns: minmax(560px, 1fr) 570px;
  gap: 80px;
  align-items: center;
  padding: 116px 20px 84px;
}

.stage-pill {
  display: inline-flex;
  margin-bottom: 24px;
  padding: 9px 16px;
  border: 1px solid rgba(47, 125, 246, 0.12);
  border-radius: 999px;
  background: rgba(234, 242, 255, 0.78);
  color: var(--pm-blue-dark);
  font-size: 13px;
  font-weight: 700;
}

.hero-copy h1 {
  max-width: 680px;
  margin: 0;
  color: var(--pm-text);
  font-size: 64px;
  font-weight: 850;
  line-height: 1.05;
  letter-spacing: -0.075em;
}

.hero-copy p {
  max-width: 560px;
  margin: 28px 0 0;
  color: var(--pm-text-secondary);
  font-size: 17px;
  line-height: 1.85;
}

.hero-actions {
  display: flex;
  gap: 16px;
  margin-top: 44px;
}

.primary-cta,
.secondary-cta {
  display: inline-flex;
  min-width: 148px;
  height: 52px;
  align-items: center;
  justify-content: center;
}

.secondary-cta {
  border: 1px solid var(--pm-border);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
}

.workspace-preview {
  padding: 28px;
  border-radius: 32px;
}

.preview-topbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 34px;
}

.mini-brand {
  width: 28px;
  height: 28px;
  border-radius: 10px;
  font-size: 10px;
}

.health-pill {
  margin-left: auto;
  padding: 8px 14px;
  border-radius: 999px;
  background: var(--pm-green-soft);
  color: var(--pm-green-dark);
  font-size: 12px;
  font-weight: 750;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
}

.metric-card,
.project-card,
.insight-card {
  border: 1px solid var(--pm-border-light);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.72);
}

.metric-card {
  padding: 18px;
}

.metric-strip {
  display: block;
  width: 34px;
  height: 5px;
  margin-bottom: 14px;
  border-radius: 999px;
}

.metric-strip.blue,
.value-icon.blue {
  background: var(--pm-blue);
}

.metric-strip.green,
.value-icon.green {
  background: var(--pm-green);
}

.metric-strip.yellow,
.value-icon.yellow {
  background: var(--pm-yellow);
}

.metric-card small {
  display: block;
  color: var(--pm-text-secondary);
  font-size: 12px;
  font-weight: 650;
}

.metric-card strong {
  display: block;
  margin-top: 8px;
  color: var(--pm-text);
  font-size: 34px;
  font-weight: 850;
}

.preview-content {
  display: grid;
  grid-template-columns: 1fr 156px;
  gap: 24px;
  margin-top: 24px;
}

.project-card {
  position: relative;
  min-height: 156px;
  padding: 28px 24px 24px;
  overflow: hidden;
}

.project-strip {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 7px;
  background: var(--pm-blue);
}

.project-card h3,
.insight-card h3,
.value-card h3 {
  margin: 0;
  color: var(--pm-text);
}

.project-card p,
.insight-card p,
.value-card p,
.section-heading p {
  color: var(--pm-text-secondary);
}

.progress-track {
  width: 72%;
  height: 8px;
  margin-top: 30px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--pm-border-light);
}

.progress-track span {
  display: block;
  width: 72%;
  height: 100%;
  border-radius: inherit;
  background: var(--pm-blue);
}

.project-card b {
  position: absolute;
  right: 22px;
  bottom: 22px;
  color: var(--pm-text);
}

.insight-card {
  padding: 22px 20px;
}

.insight-card span {
  display: block;
  width: 30px;
  height: 30px;
  margin-bottom: 14px;
  border-radius: 999px;
  background: var(--pm-yellow);
}

.insight-card p {
  margin: 10px 0 0;
  font-size: 12px;
  line-height: 1.65;
}

.capability-section {
  padding: 36px 0 0;
}

.section-heading {
  max-width: 760px;
  margin-bottom: 36px;
}

.section-heading h2 {
  margin: 0;
  color: var(--pm-text);
  font-size: 34px;
  line-height: 1.24;
  letter-spacing: -0.045em;
}

.section-heading p:last-child {
  margin-top: 14px;
  line-height: 1.8;
}

.value-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 20px;
}

.value-card {
  min-height: 158px;
  padding: 24px;
  border-radius: 24px;
}

.value-icon {
  display: block;
  width: 38px;
  height: 38px;
  margin-bottom: 18px;
  border-radius: 999px;
}

.value-card h3 {
  font-size: 18px;
}

.value-card p {
  margin: 12px 0 0;
  font-size: 13px;
  line-height: 1.7;
}
</style>
