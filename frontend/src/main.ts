import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { create, NAlert, NButton, NCard, NCheckbox, NDataTable, NDescriptions, NDescriptionsItem, NDropdown, NEmpty, NForm, NFormItem, NInput, NModal, NProgress, NResult, NSelect, NSpace, NSpin, NTab, NTabs, NTag } from 'naive-ui'
import App from './App.vue'
import { router } from './router'
import './shared/styles/global.css'
import { onUnauthorized } from './api/http'
import { useAuthStore } from './stores/auth'
import { useProjectStore } from './modules/project/store'

const app = createApp(App)

app.use(createPinia())
app.use(create({components:[NAlert, NButton, NCard, NCheckbox, NDataTable, NDescriptions, NDescriptionsItem, NDropdown, NEmpty, NForm, NFormItem, NInput, NModal, NProgress, NResult, NSelect, NSpace, NSpin, NTab, NTabs, NTag]}))
app.use(router)
onUnauthorized(() => {
  const redirect = router.currentRoute.value.fullPath
  useAuthStore().clearAuth()
  useProjectStore().$reset()
  if (!router.currentRoute.value.meta.public) void router.replace({ name: 'login', query: { redirect } })
})
app.mount('#app')
