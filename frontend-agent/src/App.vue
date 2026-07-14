<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <ProjectUploadDemoPage />
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import type { GlobalThemeOverrides } from 'naive-ui'
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import ProjectUploadDemoPage from '@/modules/project-upload/pages/ProjectUploadDemoPage.vue'

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#2f7df6',
    primaryColorHover: '#1f66d1',
    borderRadius: '12px',
    textColorBase: '#132033',
  },
}
</script>
