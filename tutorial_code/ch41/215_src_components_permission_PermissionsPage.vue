<script setup lang="ts">
import { onMounted, computed, ref } from 'vue'
import { NButton, NEmpty, NPopconfirm, useMessage } from 'naive-ui'
import { Trash2, Clock, ShieldCheck } from 'lucide-vue-next'
import { permissionApi } from '@/api/permissionApi'
import { usePermissionStore } from '@/stores/permission'

const store = usePermissionStore()
const message = useMessage()
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const list = await permissionApi.list()
    store.setRecords(list)
  } finally {
    loading.value = false
  }
})

const sessionRecords = computed(() =>
  store.records.filter(r => r.scope === 'session')
)
const foreverRecords = computed(() =>
  store.records.filter(r => r.scope === 'forever')
)

async function revoke(id: string) {
  try {
    await permissionApi.revoke(id)
    store.removeRecord(id)
    message.success('已撤回')
  } catch (e: any) {
    message.error('撤回失败: ' + e.message)
  }
}
</script>

<template>
  <div class="max-w-3xl mx-auto py-10 px-6">
    <h1 class="font-serif text-3xl text-stone-900 mb-1">权限授权</h1>
    <p class="text-sm text-stone-600 mb-8">
      管理 Athena 在你账户里的工具调用权限。撤回后,相关操作会重新要求审批。
    </p>

    <!-- 永久授权区块 -->
    <section class="mb-10">
      <h2 class="font-serif text-base text-stone-900 mb-3 flex items-center gap-2">
        <ShieldCheck :size="16" class="text-orange-600" /> 永久授权
      </h2>
      <div v-if="foreverRecords.length === 0">
        <NEmpty description="无永久授权" size="small" />
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="d in foreverRecords"
          :key="d.id"
          class="flex items-center justify-between rounded-lg
                 border border-stone-200 bg-white p-3"
        >
          <div class="min-w-0">
            <div class="font-mono text-sm text-stone-900 truncate">
              {{ d.tool_name }}
            </div>
            <div class="text-xs text-stone-500 mt-0.5">
              {{ new Date(d.created_at).toLocaleString() }}
            </div>
          </div>
          <NPopconfirm @positive-click="revoke(d.id)">
            <template #trigger>
              <NButton size="small" quaternary type="error">
                <Trash2 :size="14" /> 撤回
              </NButton>
            </template>
            确定撤回吗?
          </NPopconfirm>
        </div>
      </div>
    </section>

    <!-- 本会话授权区块 -->
    <section>
      <h2 class="font-serif text-base text-stone-900 mb-3 flex items-center gap-2">
        <Clock :size="16" class="text-stone-500" /> 本会话授权
      </h2>
      <div v-if="sessionRecords.length === 0">
        <NEmpty description="无本会话授权" size="small" />
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="d in sessionRecords"
          :key="d.id"
          class="flex items-center justify-between rounded-lg
                 border border-stone-200 bg-white p-3"
        >
          <div class="min-w-0">
            <div class="font-mono text-sm text-stone-900 truncate">
              {{ d.tool_name }}
            </div>
            <div class="text-xs text-stone-500 mt-0.5">
              {{ new Date(d.created_at).toLocaleString() }}
            </div>
          </div>
          <NButton size="small" quaternary type="error" @click="revoke(d.id)">
            <Trash2 :size="14" /> 撤回
          </NButton>
        </div>
      </div>
    </section>
  </div>
</template>