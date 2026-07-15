<template>
  <div v-if="!directory" class="picker-empty" @click="$emit('select')">
    <n-icon :size="24" color="#2f7df6"><FolderOpenOutline /></n-icon>
    <div>
      <strong>选择项目文件夹</strong>
      <p>打开本地目录选择器，选择项目根目录</p>
    </div>
  </div>
  <div v-else class="selected-directory">
    <div class="folder-mark"><n-icon :size="22"><FolderOutline /></n-icon></div>
    <div class="directory-copy">
      <strong>{{ directory.name }}</strong>
      <p>
        {{ directory.files.length }} 个文件 · {{ formatSize(directory.totalSize) }} ·
        {{ analyzableCount }} 个可解析
      </p>
    </div>
    <n-button text type="primary" @click="$emit('select')">重新选择</n-button>
    <n-button text type="error" @click="$emit('clear')">移除</n-button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { FolderOpenOutline, FolderOutline } from '@vicons/ionicons5'
import { NButton, NIcon } from 'naive-ui'
import type { SelectedDirectory } from '../types'

const props = defineProps<{ directory: SelectedDirectory | null }>()
defineEmits<{ select: []; clear: [] }>()

const analyzableCount = computed(() => props.directory?.files.filter((item) => item.analysisEligible).length || 0)

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
</script>

<style scoped>
.picker-empty,
.selected-directory {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 66px;
  padding: 14px 16px;
  border: 1px solid #bbd4ff;
  border-radius: 12px;
  background: #eef5ff;
}

.picker-empty {
  cursor: pointer;
}

.picker-empty strong,
.selected-directory strong {
  color: #1f66d1;
  font-size: 14px;
}

.picker-empty p,
.selected-directory p {
  margin: 4px 0 0;
  color: #667085;
  font-size: 12px;
}

.folder-mark {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 12px;
  color: #2f7df6;
  background: #dceaff;
}

.directory-copy {
  min-width: 0;
  flex: 1;
}
</style>
