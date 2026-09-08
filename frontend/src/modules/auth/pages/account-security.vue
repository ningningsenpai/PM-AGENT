<template>
  <section class="surface padded"><h2>修改密码</h2><p class="muted">密码长度为 6～64 位。修改密码后需要重新登录。</p>
    <RequestError :message="error" />
    <n-form ref="formRef" :model="form" :rules="rules" style="max-width:520px">
      <n-form-item v-for="item in fields" :key="item.key" :label="item.label" :path="item.key"><n-input v-model:value="form[item.key]" type="password" show-password-on="click" :input-props="{autocomplete:item.key==='oldPassword'?'current-password':'new-password'}" :maxlength="64" /></n-form-item>
      <n-button type="primary" :loading="saving" @click="save">更新密码</n-button>
    </n-form>
  </section>
</template>
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage, type FormInst, type FormRules } from 'naive-ui'
import { changePassword } from '../api'
import { useAuthStore } from '@/stores/auth'
import { useProjectStore } from '@/modules/project/store'
import RequestError from '@/shared/components/request-error.vue'
import { errorMessage } from '@/shared/utils/format'
const form=reactive({oldPassword:'',newPassword:'',confirmPassword:''}); const saving=ref(false); const error=ref('')
const formRef=ref<FormInst|null>(null); const message=useMessage(); const router=useRouter(); const auth=useAuthStore()
const fields: {key:keyof typeof form;label:string}[]=[{key:'oldPassword',label:'当前密码'},{key:'newPassword',label:'新密码'},{key:'confirmPassword',label:'确认新密码'}]
const rules:FormRules=Object.fromEntries(fields.map(f=>[f.key,[{required:true,min:6,max:64,message:'请输入 6～64 位密码',trigger:'blur'},...(f.key==='confirmPassword'?[{validator:(_:unknown,value:string)=>value===form.newPassword || new Error('两次输入的新密码不一致'),trigger:'blur'}]:[])]]))
async function save() {
  if(saving.value) return
  try { await formRef.value?.validate() } catch { return }
  saving.value=true; error.value=''
  try { await changePassword({...form}); form.oldPassword=''; form.newPassword=''; form.confirmPassword=''; auth.clearAuth(); useProjectStore().$reset(); message.success('密码已修改，请重新登录'); await router.replace('/login') }
  catch(e) { error.value=errorMessage(e) } finally { saving.value=false }
}
</script>

