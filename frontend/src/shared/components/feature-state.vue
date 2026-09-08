<template>
  <div class="page-shell">
    <div>
      <p class="eyebrow">项目空间</p>
      <h1 class="page-title">{{ title }}</h1>
    </div>
    <template v-if="route.path.startsWith('/workspace/')">
      <RequestError
        :message="store.error"
        retry
        @retry="store.loadProjects()"
      />
      <EmptyProject
        v-if="!store.projects.length && !store.loading && !store.error"
      />
      <section v-else class="surface padded">
        <n-result
          status="info"
          title="选择项目后继续"
          description="通过顶部项目选择器确定工作范围，或打开当前项目。"
        >
          <template #footer
            ><n-button
              v-if="store.currentProjectId"
              type="primary"
              @click="
                $router.push(
                  '/projects/' +
                    store.currentProjectId +
                    '/' +
                    route.meta.section,
                )
              "
              >打开当前项目</n-button
            ></template
          >
        </n-result>
      </section>
    </template>
    <section v-else class="surface padded">
      <n-result status="info" :title="title" :description="description"
        ><template #footer
          ><n-button
            v-if="route.meta.section === 'risk' && route.params.id"
            type="primary"
            @click="
              $router.push(
                '/projects/' + route.params.id + '/reports?kind=risk',
              )
            "
            >查看风险报告</n-button
          ><n-button v-else @click="$router.push('/projects')"
            >返回项目管理</n-button
          ></template
        ></n-result
      >
    </section>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import EmptyProject from './empty-project.vue'
import RequestError from './request-error.vue'
import { useProjectStore } from '@/modules/project/store'
const route = useRoute()
const store = useProjectStore()
const title = computed(() => String(route.meta.title || '页面不存在'))
const description = computed(() =>
  route.meta.section === 'risk'
    ? '当前提供基于项目资料的风险报告。风险登记、指派、确认和关闭暂未开放。'
    : route.meta.section === 'settings'
      ? '当前使用统一服务配置。模型切换、存储路径修改和更新检查暂未开放。'
      : '当前功能正在准备中，请先完成项目资料同步。',
)
</script>
