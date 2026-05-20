<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NModal, NButton, NIcon, useMessage } from 'naive-ui'
import {
  Shield, AlertTriangle, Code2, Terminal, Globe, Database,
} from 'lucide-vue-next'
import { usePermissionStore } from '@/stores/permission'
import { usePermission } from '@/composables/usePermission'
import type { Scope } from '@/api/permissionApi'

const store = usePermissionStore()
const { decide } = usePermission()
const message = useMessage()

// 当前要弹的请求(从 store 派生)
const request = computed(() => store.currentRequest)
const open = computed(() => request.value !== null)
const submitting = ref(false)

// 工具图标映射(MCP 工具用 server__tool 命名,取最后一段判断类型)
const TOOL_ICON: Record<string, any> = {
  bash_tool: Terminal,
  python_repl: Code2,
  web_search: Globe,
  postgres_query: Database,
}
const icon = computed(() => {
  if (!request.value) return Shield
  const lastSeg = request.value.tool_name.split('__').pop() ?? ''
  return TOOL_ICON[lastSeg] ?? Shield
})

const riskColors = {
  high: 'bg-red-50 text-red-600',
  medium: 'bg-amber-50 text-amber-600',
  low: 'bg-stone-100 text-stone-600',
}

async function handle(action: 'allow' | 'deny', scope: Scope = 'once') {
  if (!request.value || submitting.value) return
  submitting.value = true
  try {
    await decide(request.value.request_id, action, scope)
  } catch (e: any) {
    message.error('提交失败,请重试: ' + (e?.message ?? ''))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <NModal
    :show="open"
    preset="card"
    :mask-closable="false"
    :closable="false"
    style="width: 440px"
    :title="null"
  >
    <div v-if="request" class="space-y-4">
      <!-- 头部:图标 + 风险等级标签 -->
      <div class="flex items-center gap-3">
        <div
          class="p-2.5 rounded-lg"
          :class="riskColors[request.risk_level]"
        >
          <NIcon :component="icon" :size="20" />
        </div>
        <div>
          <h2 class="font-serif text-lg text-stone-900">批准工具调用?</h2>
          <p class="text-xs text-stone-500 mt-0.5">
            {{ request.risk_level === 'high' ? '高风险操作' :
               request.risk_level === 'medium' ? '中等风险' : '低风险' }}
          </p>
        </div>
      </div>

      <!-- 工具调用详情 -->
      <div class="rounded-lg border border-stone-200 bg-stone-50 p-3">
        <div class="font-mono text-xs text-stone-500 mb-1">
          {{ request.tool_name }}
        </div>
        <pre class="text-sm font-mono text-stone-900 whitespace-pre-wrap break-all m-0">{{ JSON.stringify(request.args, null, 2) }}</pre>
      </div>

      <p class="text-sm text-stone-700">{{ request.reason }}</p>

      <!-- 高风险警告 -->
      <div
        v-if="request.risk_level === 'high'"
        class="flex items-start gap-2 rounded-lg bg-red-50 p-3 text-xs text-red-800"
      >
        <NIcon :component="AlertTriangle" :size="16" class="shrink-0 mt-0.5" />
        <span>此操作可能产生不可逆影响。请确认参数无误后再批准。</span>
      </div>

      <!-- 按钮组 -->
      <div class="space-y-2 pt-2">
        <div class="flex gap-2">
          <NButton class="flex-1" :disabled="submitting" @click="handle('deny')">
            拒绝
          </NButton>
          <NButton
            class="flex-1"
            type="primary"
            :loading="submitting"
            @click="handle('allow', 'once')"
          >
            批准(仅此一次)
          </NButton>
        </div>
        <div class="flex gap-2">
          <NButton size="small" class="flex-1" :disabled="submitting"
                   @click="handle('allow', 'session')">
            本会话内自动批准
          </NButton>
          <NButton
            v-if="request.risk_level !== 'high'"
            size="small" class="flex-1" :disabled="submitting"
            @click="handle('allow', 'forever')"
          >
            永久批准
          </NButton>
        </div>
      </div>

      <p class="text-xs text-stone-400 text-center">
        在「偏好设置」中随时撤回授权
      </p>
    </div>
  </NModal>
</template>