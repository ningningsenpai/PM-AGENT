<template>
  <div v-if="upload" class="progress-panel">
    <div class="progress-head">
      <div>
        <strong>{{ statusLabel }}</strong>
        <p v-if="currentFile">正在处理：{{ currentFile }}</p>
      </div>
      <span>{{ progress }}%</span>
    </div>
    <n-progress type="line" :percentage="progress" :show-indicator="false" color="#2f7df6" />
    <div class="progress-stats">
      <span>成功 {{ upload.uploadedFileCount }}</span>
      <span>后台重试 {{ upload.retryFileCount }}</span>
      <span>失败 {{ upload.failedFileCount }}</span>
      <n-button v-if="upload.retryFileCount" text type="primary" @click="$emit('refresh')">刷新状态</n-button>
    </div>
    <div v-if="failedFiles.length" class="failed-list">
      <div v-for="file in failedFiles" :key="file.id">
        <span>{{ file.relativePath }}</span>
        <n-button size="tiny" type="primary" secondary @click="$emit('retry', file)">立即重试</n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NButton, NProgress } from 'naive-ui'
import type { FileUploadBatchResponse, ProjectFileResponse } from '../types'

const props = defineProps<{
  upload: FileUploadBatchResponse | null
  progress: number
  currentFile: string
}>()

defineEmits<{ refresh: []; retry: [file: ProjectFileResponse] }>()

const failedFiles = computed(() => props.upload?.files.filter((file) => file.uploadStatus === 'failed') || [])
const statusLabel = computed(() => {
  const map: Record<string, string> = {
    created: '等待上传',
    uploading: '正在上传项目文件',
    retrying: '后台正在重试 MinIO 上传',
    completed: '项目文件上传完成',
    partial_failed: '部分文件上传失败',
  }
  return map[props.upload?.status || 'created'] || '准备项目文件'
})
</script>

<style scoped>
.progress-panel {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid #e6eadf;
  border-radius: 16px;
  background: #f8faf5;
}

.progress-head,
.progress-stats,
.failed-list > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.progress-head p {
  max-width: 360px;
  margin: 4px 0 0;
  overflow: hidden;
  color: #667085;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-stats {
  justify-content: flex-start;
  color: #667085;
  font-size: 12px;
}

.failed-list {
  display: grid;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid #e6eadf;
  color: #d14343;
  font-size: 12px;
}
</style>
