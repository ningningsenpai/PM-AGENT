<template>
  <n-alert v-if="message" type="error" title="暂时无法完成操作" class="request-error">
    <span>{{ message }}</span>
    <n-button v-if="retry" size="small" secondary @click="$emit('retry')">重新加载</n-button>
  </n-alert>
</template>
<script setup lang="ts">
defineProps<{ message: string; retry?: boolean }>()
defineEmits<{ retry: [] }>()
</script>
<style scoped>
.request-error { margin-bottom: 16px; overflow-wrap: anywhere; }
.request-error :deep(button) { margin-left: 12px; }
</style>
