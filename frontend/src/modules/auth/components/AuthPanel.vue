<template>
  <n-card class="auth-panel glass-card" :bordered="false">
    <div class="panel-heading">
      <p v-if="eyebrow" class="page-eyebrow">{{ eyebrow }}</p>
      <h2>{{ title }}</h2>
      <p>{{ description }}</p>
    </div>
    <slot />
    <template v-if="$slots.footer" #footer>
      <slot name="footer" />
    </template>
  </n-card>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description: string
  eyebrow?: string
}>()
</script>

<style scoped>
.auth-panel {
  position: relative;
  z-index: 1;
  width: 448px;
  padding: 16px;
  border-radius: 28px;
}

.panel-heading {
  margin-bottom: 30px;
}

.panel-heading h2 {
  margin: 0 0 10px;
  color: var(--pm-text);
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.045em;
}

.panel-heading p:not(.page-eyebrow) {
  margin: 0;
  color: var(--pm-text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

:deep(.n-card__content) {
  padding: 28px;
}

:deep(.n-card__footer) {
  padding: 0 28px 28px;
}
</style>
