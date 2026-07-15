<template>
  <div class="workspace-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark"><span>PM</span><i></i><b></b></div>
        <div><strong>PM-Agent</strong><small>项目工作台</small></div>
      </div>
      <nav>
        <a>个人工作台</a>
        <a class="active">项目管理</a>
        <a>任务看板</a>
        <a>风控中心</a>
        <a>PM助手</a>
        <a>知识库</a>
        <a>报告中心</a>
      </nav>
      <div class="sidebar-note">文件上传联调客户端</div>
    </aside>

    <main>
      <header class="topbar">
        <div class="search">搜索项目、任务、风险或报告</div>
        <div class="profile"><span>宁</span><div><strong>宁宁</strong><small>个人项目</small></div></div>
      </header>
      <section class="content">
        <div class="page-head">
          <div><p>PROJECT WORKSPACE</p><h1>项目管理</h1></div>
          <n-button type="primary" size="large" @click="openModal">新建项目</n-button>
        </div>
        <div class="hero-card">
          <div>
            <span class="eyebrow">可靠上传链路</span>
            <h2>从本地项目目录，到可验证的 MinIO 对象</h2>
            <p>选择项目根目录后，客户端会保留相对路径并逐文件上传；临时故障由前端和 RabbitMQ 分层重试。</p>
            <n-button type="primary" @click="openModal">开始新建项目</n-button>
          </div>
          <div class="trace-card">
            <div><i class="blue"></i><span>选择根目录</span><b>前端</b></div>
            <div><i class="green"></i><span>暂存并生成指纹</span><b>Java</b></div>
            <div><i class="yellow"></i><span>MinIO 对账与重试</span><b>MQ</b></div>
          </div>
        </div>
        <div class="metrics">
          <article><span>单文件上限</span><strong>50 MB</strong></article>
          <article><span>单次目录</span><strong>5000</strong><small>个文件</small></article>
          <article><span>自动重试</span><strong>3</strong><small>级延迟</small></article>
        </div>
      </section>
    </main>

    <NewProjectModal v-model:show="showModal" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { NButton } from 'naive-ui'
import NewProjectModal from '../components/NewProjectModal.vue'
import { useProjectUploadStore } from '../store'

const showModal = ref(true)
const store = useProjectUploadStore()

function openModal() {
  store.reset()
  showModal.value = true
}
</script>

<style scoped>
.workspace-shell {
  display: grid;
  min-height: 100vh;
  grid-template-columns: 248px 1fr;
  background:
    radial-gradient(circle at 78% 16%, rgba(47, 125, 246, 0.09), transparent 28%),
    radial-gradient(circle at 42% 82%, rgba(38, 185, 131, 0.08), transparent 25%),
    #f8faf5;
}

.sidebar {
  position: relative;
  padding: 32px 24px;
  border-right: 1px solid #eef2ea;
  background: rgba(255, 255, 255, 0.92);
}

.brand,
.profile {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-mark {
  position: relative;
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  overflow: hidden;
  border-radius: 14px;
  color: white;
  background: #132033;
}

.brand-mark span { z-index: 2; font-size: 10px; font-weight: 800; }
.brand-mark i,
.brand-mark b { position: absolute; width: 18px; height: 18px; border-radius: 50%; }
.brand-mark i { top: 5px; left: 6px; border: 3px solid #2f7df6; }
.brand-mark b { right: 5px; bottom: 5px; border: 3px solid #26b983; }
.brand strong,
.brand small,
.profile strong,
.profile small { display: block; }
.brand small,
.profile small { margin-top: 3px; color: #667085; font-size: 11px; }

nav {
  display: grid;
  gap: 6px;
  margin-top: 52px;
}

nav a {
  padding: 13px 18px;
  border-radius: 12px;
  color: #667085;
  font-size: 14px;
}

nav a.active {
  color: #2f7df6;
  font-weight: 700;
  background: #eaf2ff;
}

.sidebar-note {
  position: absolute;
  right: 24px;
  bottom: 28px;
  left: 24px;
  padding: 14px;
  border-radius: 14px;
  color: #667085;
  background: #f8faf5;
  font-size: 12px;
  text-align: center;
}

main { min-width: 0; }

.topbar {
  display: flex;
  height: 82px;
  padding: 20px 38px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(230, 234, 223, 0.7);
}

.search {
  width: 360px;
  padding: 13px 18px;
  border: 1px solid #e6eadf;
  border-radius: 14px;
  color: #98a2b3;
  background: rgba(255, 255, 255, 0.72);
  font-size: 13px;
}

.profile > span {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: 50%;
  color: white;
  background: #2f7df6;
}

.content { padding: 48px 52px; }
.page-head { display: flex; align-items: flex-end; justify-content: space-between; }
.page-head p,
.eyebrow { margin: 0 0 8px; color: #2f7df6; font-size: 11px; font-weight: 800; letter-spacing: 0.14em; }
.page-head h1 { margin: 0; font-size: 32px; letter-spacing: -0.05em; }
.hero-card {
  display: grid;
  margin-top: 34px;
  padding: 42px;
  grid-template-columns: 1.3fr 0.7fr;
  gap: 50px;
  border: 1px solid #e6eadf;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.84);
  box-shadow: 0 20px 60px rgba(19, 32, 51, 0.07);
}
.hero-card h2 { max-width: 620px; margin: 10px 0 14px; font-size: 34px; line-height: 1.2; letter-spacing: -0.05em; }
.hero-card p { max-width: 620px; margin: 0 0 28px; color: #667085; line-height: 1.8; }
.trace-card { display: grid; align-content: center; gap: 12px; }
.trace-card div { display: grid; padding: 16px; grid-template-columns: 12px 1fr auto; align-items: center; gap: 12px; border-radius: 16px; background: #f8faf5; }
.trace-card i { width: 10px; height: 10px; border-radius: 50%; }
.trace-card .blue { background: #2f7df6; }
.trace-card .green { background: #26b983; }
.trace-card .yellow { background: #f5b83d; }
.trace-card b { color: #98a2b3; font-size: 11px; }
.metrics { display: grid; margin-top: 20px; grid-template-columns: repeat(3, 1fr); gap: 18px; }
.metrics article { padding: 24px; border: 1px solid #eef2ea; border-radius: 20px; background: rgba(255, 255, 255, 0.7); }
.metrics span { display: block; color: #667085; font-size: 12px; }
.metrics strong { display: inline-block; margin-top: 10px; font-size: 28px; }
.metrics small { margin-left: 8px; color: #98a2b3; }
</style>
