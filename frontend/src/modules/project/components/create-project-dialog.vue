<template>
  <n-modal
    :show="show"
    preset="card"
    title="创建项目"
    style="width: 560px"
    :mask-closable="!saving"
    :closable="!saving"
    @update:show="$emit('update:show', $event)"
  >
    <p class="muted">为项目命名并绑定本地项目文件夹，创建成功后将自动同步源码和文档。</p>
    <n-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-placement="top"
      @submit.prevent="save"
    >
      <n-form-item label="项目名称" path="projectName">
        <n-input
          v-model:value="form.projectName"
          :maxlength="128"
          placeholder="例如：PM-AGENT 平台 MVP"
          autofocus
        />
      </n-form-item>
      <n-form-item
        label="项目文件夹"
        :validation-status="folderError ? 'error' : undefined"
        :feedback="folderError"
      >
        <div class="directory-field">
          <template v-if="selectedDirectoryName">
            <div class="directory-summary">
              <span class="directory-mark" aria-hidden="true">⌂</span>
              <div>
                <strong>{{ selectedDirectoryName }}</strong>
                <p>{{ pickerSupported ? '已绑定到当前浏览器' : '当前页面已选择，刷新后需重新选择' }}</p>
              </div>
              <n-tag type="success" round size="small">已选择</n-tag>
            </div>
            <n-space>
              <n-button size="small" :disabled="saving || selecting" @click="selectDirectory">
                重新选择
              </n-button>
              <n-button size="small" :disabled="saving || selecting" @click="removeDirectory">
                移除
              </n-button>
            </n-space>
          </template>
          <n-button
            v-else
            class="directory-select"
            secondary
            type="primary"
            :loading="selecting"
            :disabled="saving"
            @click="selectDirectory"
          >
            选择项目文件夹
          </n-button>
          <input
            ref="directoryInput"
            class="directory-input"
            type="file"
            multiple
            directory=""
            webkitdirectory=""
            @change="handleFallbackDirectoryChange"
          />
        </div>
      </n-form-item>
      <n-alert type="info" :show-icon="false">
        仅保存浏览器授予的目录访问句柄，不上传本机绝对路径。项目文件同步到服务端后，内容解析仍由项目详情页单独发起。
      </n-alert>
      <RequestError :message="error" />
      <n-space class="dialog-actions" justify="end">
        <n-button :disabled="saving" @click="$emit('update:show', false)">取消</n-button>
        <n-button type="primary" attr-type="submit" :loading="saving">
          创建并同步
        </n-button>
      </n-space>
    </n-form>
  </n-modal>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import type { FormInst, FormRules } from 'naive-ui'
import { useMessage } from 'naive-ui'
import { createProject } from '../api'
import {
  isDirectoryPickerCancelled,
  isProjectDirectoryPickerSupported,
  pickProjectDirectory,
  rememberPendingProjectDirectory,
  saveProjectDirectoryBinding,
  type ProjectDirectoryHandle,
} from '../project-directory'
import {
  projectFileCandidatesFromInput,
  type ProjectFileCandidate,
} from '../file-upload'
import { useAuthStore } from '@/stores/auth'
import RequestError from '@/shared/components/request-error.vue'
import { errorMessage } from '@/shared/utils/format'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{
  'update:show': [value: boolean]
  created: [id: string]
}>()
const auth = useAuthStore()
const message = useMessage()
const form = reactive({ projectName: '' })
const saving = ref(false)
const selecting = ref(false)
const error = ref('')
const folderError = ref('')
const formRef = ref<FormInst | null>(null)
const directoryInput = ref<HTMLInputElement | null>(null)
const selectedDirectoryName = ref('')
const directoryHandle = ref<ProjectDirectoryHandle | null>(null)
const fallbackFiles = ref<ProjectFileCandidate[]>([])
const pickerSupported = isProjectDirectoryPickerSupported()
const rules: FormRules = {
  projectName: {
    required: true,
    validator: (_, value: string) =>
      Boolean(value?.trim()) || new Error('请输入项目名称'),
    trigger: 'blur',
  },
}

watch(
  () => props.show,
  (show) => {
    if (show) resetForm()
  },
)

async function selectDirectory() {
  if (saving.value || selecting.value) return
  folderError.value = ''
  if (!pickerSupported) {
    if (directoryInput.value) {
      directoryInput.value.value = ''
      directoryInput.value.click()
    }
    return
  }

  selecting.value = true
  try {
    const handle = await pickProjectDirectory(directoryHandle.value ?? undefined)
    directoryHandle.value = handle
    fallbackFiles.value = []
    selectedDirectoryName.value = handle.name
  } catch (selectionError) {
    if (!isDirectoryPickerCancelled(selectionError)) {
      folderError.value = errorMessage(selectionError)
    }
  } finally {
    selecting.value = false
  }
}

function handleFallbackDirectoryChange(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  if (!files.length) return
  fallbackFiles.value = projectFileCandidatesFromInput(files)
  directoryHandle.value = null
  selectedDirectoryName.value = getDirectoryName(files[0])
  folderError.value = ''
}

function removeDirectory() {
  directoryHandle.value = null
  fallbackFiles.value = []
  selectedDirectoryName.value = ''
  folderError.value = ''
}

async function save() {
  if (saving.value) return
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  if (!selectedDirectoryName.value) {
    folderError.value = '请选择项目文件夹'
    return
  }

  saving.value = true
  error.value = ''
  try {
    const project = await createProject({
      projectName: form.projectName.trim(),
    })
    const selection = directoryHandle.value
      ? { directoryName: selectedDirectoryName.value, handle: directoryHandle.value }
      : { directoryName: selectedDirectoryName.value, files: fallbackFiles.value }
    rememberPendingProjectDirectory(project.id, selection)

    if (directoryHandle.value && auth.user?.id) {
      try {
        await saveProjectDirectoryBinding(auth.user.id, project.id, directoryHandle.value)
      } catch {
        message.warning('项目已创建，但浏览器未能持久保存文件夹；本次仍会继续同步')
      }
    }

    emit('update:show', false)
    emit('created', project.id)
  } catch (saveError) {
    error.value = errorMessage(saveError)
  } finally {
    saving.value = false
  }
}

function resetForm() {
  form.projectName = ''
  error.value = ''
  folderError.value = ''
  selectedDirectoryName.value = ''
  directoryHandle.value = null
  fallbackFiles.value = []
  if (directoryInput.value) directoryInput.value.value = ''
}

function getDirectoryName(file: File) {
  const [directoryName] = file.webkitRelativePath.split('/')
  return directoryName || '项目文件夹'
}
</script>

<style scoped>
.directory-field {
  display: grid;
  width: 100%;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--pm-border-light);
  border-radius: 14px;
  background: #f8faf5;
}

.directory-summary {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
}

.directory-summary strong {
  overflow-wrap: anywhere;
}

.directory-summary p {
  margin: 3px 0 0;
  color: var(--pm-text-muted);
  font-size: 12px;
}

.directory-mark {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border-radius: 12px;
  background: #e9f2ff;
  color: var(--pm-blue-dark);
  font-size: 20px;
}

.directory-select {
  min-height: 44px;
}

.directory-input {
  display: none;
}

.dialog-actions {
  margin-top: 20px;
}
</style>
