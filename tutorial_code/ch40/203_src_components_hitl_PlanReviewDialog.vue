<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { NModal, NButton, NInput, NIcon, useMessage } from 'naive-ui'
import { Check, X, Edit3, Clock } from 'lucide-vue-next'
import { apiClient } from '@/api/client'

const props = defineProps<{
  taskId: string
  plan: { topics: string[]; rationale: string }
  deadlineSec: number
}>()

const emit = defineEmits<{
  resolved: []
}>()

const open = ref(true)
const editing = ref(false)
const editedTopics = ref<string[]>([...props.plan.topics])
const submitting = ref(false)
const remaining = ref(props.deadlineSec)
const message = useMessage()

// 倒计时:超时自动 approve(后端也有兜底,前端只是给用户看)
let timerId: number | undefined
onMounted(() => {
  timerId = window.setInterval(() => {
    if (remaining.value <= 1) {
      window.clearInterval(timerId)
      handleDecision('approve')
    } else {
      remaining.value--
    }
  }, 1000)
})
onUnmounted(() => {
  if (timerId) window.clearInterval(timerId)
})

const timerLabel = computed(() => {
  const m = Math.floor(remaining.value / 60)
  const s = String(remaining.value % 60).padStart(2, '0')
  return `${m}:${s}`
})

const hasChanges = computed(() =>
  JSON.stringify(editedTopics.value) !== JSON.stringify(props.plan.topics)
)

async function handleDecision(action: 'approve' | 'modify' | 'reject') {
  if (submitting.value) return
  submitting.value = true
  try {
    await apiClient.submitPlanDecision(props.taskId, {
      action,
      modified_topics: action === 'modify' ? editedTopics.value : null,
    })
    open.value = false
    emit('resolved')
  } catch (e: any) {
    message.error('提交失败: ' + e.message)
  } finally {
    submitting.value = false
  }
}

function addTopic() {
  editedTopics.value.push('')
}

function removeTopic(idx: number) {
  editedTopics.value.splice(idx, 1)
}
</script>

<template>
  <NModal
    v-model:show="open"
    preset="card"
    :mask-closable="false"
    :closable="false"
    style="width: 640px"
    title="Planner 拟定了研究计划"
  >
    <!-- 倒计时 -->
    <template #header-extra>
      <div class="flex items-center gap-1.5 px-2.5 py-1 rounded-full
                  bg-amber-50 text-amber-700 text-xs font-medium">
        <NIcon :component="Clock" :size="14" />
        <span class="font-mono">{{ timerLabel }}</span>
      </div>
    </template>

    <p class="text-sm text-stone-600 mb-4">{{ plan.rationale }}</p>

    <!-- 计划列表(可编辑) -->
    <div class="space-y-2 mb-6">
      <div
        v-for="(topic, i) in editedTopics"
        :key="i"
        class="flex items-center gap-2 rounded-lg border border-stone-200
               bg-white p-2 group"
      >
        <span class="shrink-0 inline-flex w-6 h-6 items-center justify-center
                     rounded-full bg-orange-100 text-orange-700 text-xs font-semibold">
          {{ i + 1 }}
        </span>
        <NInput
          v-model:value="editedTopics[i]"
          :bordered="false"
          @focus="editing = true"
        />
        <button
          v-if="editedTopics.length > 1"
          class="opacity-0 group-hover:opacity-100 transition text-stone-400 hover:text-red-600"
          @click="removeTopic(i)"
        >
          <NIcon :component="X" :size="16" />
        </button>
      </div>

      <button
        class="w-full flex items-center justify-center gap-1.5 py-2
               rounded-lg border-2 border-dashed border-stone-200
               text-sm text-stone-400 hover:border-stone-300 hover:text-stone-600
               transition"
        @click="addTopic"
      >
        + 添加方向
      </button>
    </div>

    <!-- 按钮组 -->
    <template #footer>
      <div class="flex justify-end gap-2">
        <NButton :disabled="submitting" @click="handleDecision('reject')">
          拒绝重做
        </NButton>
        <NButton
          v-if="hasChanges"
          type="primary"
          :loading="submitting"
          @click="handleDecision('modify')"
        >
          使用修改后的计划
        </NButton>
        <NButton
          v-else
          type="primary"
          :loading="submitting"
          @click="handleDecision('approve')"
        >
          批准并开始
        </NButton>
      </div>
    </template>
  </NModal>
</template>