<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <router-view />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { NConfigProvider, NDialogProvider, NMessageProvider } from 'naive-ui'
import type { GlobalThemeOverrides } from 'naive-ui'

const productFont = 'MiSans, "HarmonyOS Sans SC", "Microsoft YaHei", Inter, sans-serif'

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#2F7DF6',
    primaryColorHover: '#1F66D1',
    primaryColorPressed: '#1558B8',
    primaryColorSuppl: '#2F7DF6',
    successColor: '#26B983',
    successColorHover: '#15966A',
    warningColor: '#F5B83D',
    warningColorHover: '#D8911E',
    borderRadius: '12px',
    fontFamily: productFont,
  },
  Card: {
    borderRadius: '20px',
  },
  Button: {
    borderRadiusMedium: '12px',
    borderRadiusLarge: '14px',
  },
  Input: {
    borderRadius: '12px',
  },
}
</script>
