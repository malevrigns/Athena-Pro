<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, CloseBold, Promotion } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useTaskStore } from '@/stores/task'
import { useSessionStore } from '@/stores/session'

const MIN_QUESTION_LENGTH = 8
const router = useRouter()
const store = useTaskStore()
const session = useSessionStore()
const question = ref('调研 2026 年大模型 Agent 框架的发展现状、技术路线和企业落地场景')

const presets = [
  '调研 2026 年大模型 Agent 框架的发展现状与技术路线',
  '比较 LangGraph、CrewAI、AutoGen、Strands 的多 Agent 编排能力',
  '深度研究 RAG 在金融客服中的落地架构与评估指标',
  '调研边缘端轻量模型 (Phi、Llama 3.x) 的部署最佳实践',
  '盘点 2026 年开源 RAG 评估框架与可观测平台',
]

const charCount = computed(() => question.value.length)
const canSubmit = computed(() => charCount.value >= MIN_QUESTION_LENGTH && !store.loading && !store.isRunning)

async function submit() {
  if (store.loading || store.isRunning) return
  const trimmed = question.value.trim()
  if (trimmed.length < MIN_QUESTION_LENGTH) {
    ElMessage.warning(`请至少输入 ${MIN_QUESTION_LENGTH} 个字符后再开始研究`)
    return
  }
  if (session.config?.require_auth && !session.hasApiKey) {
    ElMessage.warning('请先到「系统设置」配置 API Key')
    router.push({ name: 'settings', query: { next: '/workbench' } })
    return
  }
  try {
    await store.start(trimmed, session.userId)
    if (store.error) ElMessage.error(store.error)
    else if (store.current?.id) {
      ElMessage.success(`任务已启动 · ${store.current.id}`)
      router.push(`/workbench/${store.current.id}`)
    }
  } catch (err) {
    ElMessage.error((err as Error).message)
  }
}

async function stop() {
  try {
    await store.stop()
    ElMessage.info('已发送中断信号')
  } catch (err) {
    ElMessage.error((err as Error).message)
  }
}
</script>

<template>
  <ElCard shadow="never" class="composer-card">
    <template #header>
      <div class="composer-head">
        <div>
          <div class="badges">
            <ElTag type="success" effect="dark" size="small" round>Production v5</ElTag>
            <ElTag effect="plain" size="small" round>多 Agent · 迭代式</ElTag>
          </div>
          <h2>一句话开题, <span class="gradient-text">深度研究自动跑完</span></h2>
          <p class="sub">Planner → Researcher (并发) → Quality Gate → Reviewer → Writer。 SSE 实时流, 全程持久化, 导出 MD / PDF / DOCX。</p>
        </div>
      </div>
    </template>

    <ElInput
      v-model="question"
      type="textarea"
      :autosize="{ minRows: 4, maxRows: 8 }"
      placeholder="例: 调研 2026 年企业级 RAG 平台的成本结构与评估方法 …"
      :disabled="store.isRunning"
      maxlength="2000"
      show-word-limit
      resize="none"
    />

    <div class="preset-row">
      <span class="preset-label">快速预设</span>
      <ElTag
        v-for="p in presets"
        :key="p"
        type="info"
        effect="plain"
        round
        class="preset-chip"
        @click="question = p"
      >
        {{ p }}
      </ElTag>
    </div>

    <div class="action-row">
      <div class="hint">
        <span class="dot" :class="{ live: store.isRunning, idle: !canSubmit && !store.isRunning }" />
        <span v-if="store.isRunning">研究中 · SSE 流式更新</span>
        <span v-else-if="canSubmit">就绪 · 平均 30–90 秒 / 任务</span>
        <span v-else>问题至少 8 字</span>
      </div>
      <div class="actions">
        <ElButton v-if="store.isRunning" type="danger" plain :icon="CloseBold" @click="stop">中断任务</ElButton>
        <ElButton
          type="primary"
          size="large"
          :icon="store.isRunning ? Promotion : ArrowRight"
          :loading="store.loading || store.isRunning"
          :disabled="store.loading || store.isRunning"
          @click="submit"
        >
          {{ store.isRunning ? '研究中…' : '开始研究' }}
        </ElButton>
      </div>
    </div>

    <ElAlert v-if="store.error" type="error" :title="store.error" show-icon style="margin-top: 12px;" />
  </ElCard>
</template>

<style scoped>
.composer-card {
  border-radius: 14px !important;
  border: 1px solid var(--athena-border);
  background: var(--athena-surface);
  overflow: hidden;
}
.composer-card :deep(.el-card__header) {
  background: linear-gradient(135deg, rgba(99,102,241,.06), rgba(236,72,153,.04));
  border-bottom: 1px solid var(--athena-border);
  padding: 20px 22px;
}
.composer-card :deep(.el-card__body) { padding: 18px 22px 22px; display: grid; gap: 14px; }

.composer-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; flex-wrap: wrap; }
.badges { display: flex; gap: 8px; flex-wrap: wrap; }
.composer-head h2 {
  margin: 12px 0 4px;
  font-size: clamp(20px, 2.2vw, 26px);
  letter-spacing: -.02em;
  font-weight: 700;
}
.gradient-text {
  background: var(--athena-gradient);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.composer-head .sub { margin: 0; color: var(--athena-muted); font-size: 13px; line-height: 1.6; max-width: 720px; }

.preset-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.preset-label {
  font-family: var(--athena-mono);
  font-size: 11px;
  letter-spacing: .12em;
  color: var(--athena-muted);
  margin-right: 4px;
}
.preset-chip {
  cursor: pointer;
  transition: all .12s ease;
}
.preset-chip:hover {
  background: var(--el-color-primary-light-9) !important;
  color: var(--el-color-primary) !important;
  border-color: var(--el-color-primary-light-7) !important;
  transform: translateY(-1px);
}

.action-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.hint { display: inline-flex; align-items: center; gap: 8px; color: var(--athena-muted); font-size: 13px; }
.hint .dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--el-color-success);
  box-shadow: 0 0 0 4px rgba(16,185,129,.18);
}
.hint .dot.live { background: var(--el-color-primary); box-shadow: 0 0 0 4px rgba(99,102,241,.2); animation: pulse 1.6s ease-in-out infinite; }
.hint .dot.idle { background: var(--el-color-warning); box-shadow: 0 0 0 4px rgba(245,158,11,.18); }
.actions { display: flex; gap: 10px; }

@keyframes pulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.3); } }
</style>
