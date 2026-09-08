<template>
  <section class="surface empty-project">
    <span class="eyebrow">从第一个项目开始</span>
    <h2>让项目资料成为可追踪的执行线索</h2>
    <p>创建项目并上传源码或文档，即可与 PM 助手讨论项目，沉淀决策并生成报告。</p>
    <div class="journey"><span>01 创建项目</span><span>02 同步与解析</span><span>03 问答与报告</span></div>
    <n-button type="primary" size="large" @click="$router.push('/projects?create=1')">创建第一个项目</n-button>
  </section>
</template>
<style scoped>
.empty-project { padding: 64px 40px; text-align: center; }
h2 { margin: 16px 0; font-size: 28px; } p { color: var(--pm-text-secondary); }
.journey { display: flex; justify-content: center; gap: 40px; margin: 36px 0; color: var(--pm-blue-dark); }
</style>
