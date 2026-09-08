<template>
  <n-modal :show="show" preset="card" title="创建项目" style="width: 480px" :mask-closable="!saving" :closable="!saving" @update:show="$emit('update:show', $event)">
    <p class="muted">先为项目命名，随后上传源码或文档，开始积累项目上下文。</p>
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" @submit.prevent="save">
      <n-form-item label="项目名称" path="projectName"><n-input v-model:value="form.projectName" :maxlength="128" placeholder="例如：PM-Agent 平台 MVP" autofocus /></n-form-item>
      <RequestError :message="error" />
      <n-space justify="end"><n-button :disabled="saving" @click="$emit('update:show', false)">取消</n-button><n-button type="primary" attr-type="submit" :loading="saving">创建并进入项目</n-button></n-space>
    </n-form>
  </n-modal>
</template>
<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import type { FormInst, FormRules } from 'naive-ui'
import { createProject } from '../api'
import RequestError from '@/shared/components/request-error.vue'
import { errorMessage } from '@/shared/utils/format'
const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ 'update:show': [value: boolean]; created: [id: string] }>()
const form = reactive({ projectName: '' }); const saving = ref(false); const error = ref(''); const formRef = ref<FormInst | null>(null)
const rules: FormRules = { projectName: { required: true, validator: (_, value: string) => Boolean(value?.trim()) || new Error('请输入项目名称'), trigger: 'blur' } }
watch(() => props.show, (show) => { if (show) { form.projectName = ''; error.value = '' } })
async function save() {
  if (saving.value) return
  try { await formRef.value?.validate() } catch { return }
  saving.value = true; error.value = ''
  try { const project = await createProject({ projectName: form.projectName.trim() }); emit('update:show', false); emit('created', project.id) }
  catch (e) { error.value = errorMessage(e) } finally { saving.value = false }
}
</script>
