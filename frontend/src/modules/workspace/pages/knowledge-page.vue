<template>
  <div class="page-shell">
    <div class="page-title-row">
      <div>
        <p class="eyebrow">项目知识</p>
        <h1 class="page-title">知识库</h1>
        <p class="page-description">
          统一查看项目文件和已记录的项目上下文，保留原始来源。
        </p>
      </div>
      <RouterLink :to="'/projects/' + projectId">同步项目文件 →</RouterLink>
    </div>
    <n-tabs v-model:value="tab"
      ><n-tab name="files">项目文件</n-tab
      ><n-tab name="context">已记录内容</n-tab></n-tabs
    ><ProjectFileList
      v-show="tab === 'files'"
      :project-id="projectId"
      :disabled="contextBusy"
      @busy="fileBusy = $event"
    />
    <section v-show="tab === 'context'" class="surface padded">
      <ContextEntries
        :project-id="projectId"
        :disabled="fileBusy"
        @busy="contextBusy = $event"
      />
    </section>
    <p class="muted">外部知识源导入、独立文件夹与向量检索配置暂未开放。</p>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import ProjectFileList from '@/modules/project/components/project-file-list.vue'
import ContextEntries from '@/modules/assistant/components/context-entries.vue'
const projectId = String(useRoute().params.id)
const tab = ref('files')
const fileBusy = ref(false)
const contextBusy = ref(false)
</script>
