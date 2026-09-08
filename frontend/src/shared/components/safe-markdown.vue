<template><div class="markdown-content" v-html="renderMarkdown(content)" /></template>
<script setup lang="ts">
import { renderMarkdown } from '../utils/markdown'
defineProps<{content:string}>()
</script>
<style scoped>
.markdown-content { overflow-wrap:anywhere;line-height:1.85;color:var(--pm-text);font-size:14px; }
.markdown-content :deep(> :first-child) { margin-top:0; } .markdown-content :deep(> :last-child) { margin-bottom:0; }
.markdown-content :deep(pre) { background:var(--pm-bg);border:1px solid var(--pm-border);border-radius:10px;padding:16px;overflow:auto;max-width:100%; }
.markdown-content :deep(code) { font-size:12px;font-family:Consolas,monospace; } .markdown-content :deep(table) { display:block;overflow:auto;border-collapse:collapse; }
.markdown-content :deep(th),.markdown-content :deep(td) { border:1px solid var(--pm-border);padding:8px 12px; }
.markdown-content :deep(blockquote) { border-left:3px solid var(--pm-green);margin:16px 0;padding-left:16px;color:var(--pm-text-secondary); }
.markdown-content :deep(h1) { font-size:24px; } .markdown-content :deep(h2) { font-size:20px; } .markdown-content :deep(h3) { font-size:17px; }
</style>

