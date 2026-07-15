<template>
  <n-modal :show="show" :mask-closable="false" @update:show="$emit('update:show', $event)">
    <div class="project-modal">
      <div class="modal-head">
        <div>
          <h2>新建项目</h2>
          <p>创建项目基础信息，并选择需要上传和分析的项目根目录。</p>
        </div>
        <n-button quaternary circle :disabled="store.submitting" @click="$emit('update:show', false)">
          <template #icon><n-icon><CloseOutline /></n-icon></template>
        </n-button>
      </div>

      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
        <n-form-item label="项目名称" path="name">
          <n-input v-model:value="form.name" placeholder="例如：PM-Agent 平台 MVP" />
        </n-form-item>
        <n-form-item label="项目文件夹" required>
          <ProjectDirectoryPicker
            :directory="selectedDirectory"
            @select="handleSelectDirectory"
            @clear="clearDirectory"
          />
        </n-form-item>
        <n-form-item label="项目周期">
          <n-date-picker v-model:value="dateRange" type="daterange" clearable style="width: 100%" />
        </n-form-item>
        <n-form-item label="项目说明">
          <n-input
            v-model:value="form.description"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 4 }"
            placeholder="说明项目目标和当前阶段范围"
          />
        </n-form-item>
      </n-form>

      <FileUploadProgress
        :upload="store.upload"
        :progress="store.progress"
        :current-file="store.currentFile"
        @refresh="store.refresh"
        @retry="store.retry"
      />

      <div class="modal-actions">
        <n-button :disabled="store.submitting" @click="$emit('update:show', false)">取消</n-button>
        <n-button type="primary" :loading="store.submitting" @click="handleSubmit">
          {{ store.submitting ? '正在创建并上传' : '创建项目' }}
        </n-button>
      </div>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { CloseOutline } from '@vicons/ionicons5'
import type { FormInst, FormRules } from 'naive-ui'
import { NButton, NDatePicker, NForm, NFormItem, NIcon, NInput, NModal, useMessage } from 'naive-ui'
import ProjectDirectoryPicker from './ProjectDirectoryPicker.vue'
import FileUploadProgress from './FileUploadProgress.vue'
import { useDirectoryPicker } from '../composables/use-directory-picker'
import { useProjectUploadStore } from '../store'

defineProps<{ show: boolean }>()
const emit = defineEmits<{ 'update:show': [value: boolean] }>()

const message = useMessage()
const store = useProjectUploadStore()
const formRef = ref<FormInst | null>(null)
const dateRange = ref<[number, number] | null>(null)
const form = reactive({ name: '', description: '', startDate: null as string | null, endDate: null as string | null })
const { selectedDirectory, selectDirectory, clearDirectory } = useDirectoryPicker()
const rules: FormRules = {
  name: { required: true, message: '请输入项目名称', trigger: ['input', 'blur'] },
}

watch(dateRange, (value) => {
  form.startDate = value ? formatDate(value[0]) : null
  form.endDate = value ? formatDate(value[1]) : null
})

async function handleSelectDirectory() {
  try {
    await selectDirectory()
  } catch (error) {
    message.error((error as Error).message || '无法读取所选目录')
  }
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
    if (!selectedDirectory.value) {
      message.warning('请选择项目文件夹')
      return
    }
    await store.submit(form, selectedDirectory.value)
    if (store.upload?.status === 'completed') {
      message.success('项目文件已上传并通过 MinIO 对账')
    } else if (store.upload?.status === 'retrying') {
      message.warning('项目已创建，部分文件正在后台重试')
    } else {
      message.warning('项目已保留，请处理失败文件后继续')
    }
  } catch (error) {
    const candidate = error as { userMessage?: string; message?: string }
    message.error(candidate.userMessage || candidate.message || '创建项目失败')
  }
}

function formatDate(value: number) {
  const date = new Date(value)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}
</script>

<style scoped>
.project-modal {
  width: 560px;
  max-height: calc(100vh - 80px);
  padding: 34px 38px 30px;
  overflow-y: auto;
  border-radius: 28px;
  background: #fff;
  box-shadow: 0 24px 70px rgba(19, 32, 51, 0.2);
}

.modal-head,
.modal-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.modal-head {
  margin-bottom: 26px;
}

.modal-head h2 {
  margin: 0;
  font-size: 25px;
  letter-spacing: -0.04em;
}

.modal-head p {
  margin: 8px 0 0;
  color: #667085;
  font-size: 13px;
}

.modal-actions {
  justify-content: flex-end;
  margin-top: 24px;
}

.modal-actions :deep(.n-button) {
  min-width: 116px;
  height: 44px;
  border-radius: 14px;
}
</style>
