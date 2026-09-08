<template><n-tag :type="status === 'active' ? 'success' : status === 'init_failed' ? 'error' : 'info'" round size="small">{{ labels[status] || '未知状态' }}</n-tag></template>
<script setup lang="ts">
defineProps<{ status: string }>()
const labels: Record<string, string> = { active: '已初始化', initializing: '初始化中', init_failed: '初始化失败' }
</script>
