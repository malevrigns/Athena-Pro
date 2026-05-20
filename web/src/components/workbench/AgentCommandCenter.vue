<script setup lang="ts">
import { ref, watch } from 'vue'
import { agentApi, type AgentTraceItem, type AgentTraceSummary, type AgentTraceStatus } from '@/api/agents'
import './AgentCommandCenter.css'

const props = defineProps<{
  taskId?: string
  refreshKey?: string
}>()

const emptySummary: AgentTraceSummary = {
  total_agents: 0,
  completed_agents: 0,
  running_agents: 0,
  queued_agents: 0,
  skipped_agents: 0,
  failed_agents: 0,
  source_count: 0,
  knowledge_hits: 0,
  total_tokens: 0,
  total_cost_usd: 0,
  capability_count: 0,
  tool_count: 0,
}
const items = ref<AgentTraceItem[]>([])
const summary = ref<AgentTraceSummary>({ ...emptySummary })
const error = ref('')
let requestSeq = 0

watch(
  () => [props.taskId, props.refreshKey],
  ([taskId]) => {
    if (typeof taskId !== 'string' || !taskId) {
      resetTrace()
      return
    }
    loadTrace(taskId)
  },
  { immediate: true },
)

async function loadTrace(taskId: string) {
  const seq = ++requestSeq
  error.value = ''
  try {
    const response = await agentApi.trace(taskId)
    if (seq !== requestSeq) return
    items.value = response.items
    summary.value = response.summary
  } catch (err) {
    if (seq !== requestSeq) return
    resetTrace()
    error.value = err instanceof Error ? err.message : String(err)
  }
}

function resetTrace() {
  items.value = []
  summary.value = { ...emptySummary }
}

function statusLabel(status: AgentTraceStatus): string {
  const labels: Record<AgentTraceStatus, string> = {
    queued: '排队',
    running: '运行中',
    done: '完成',
    skipped: '跳过',
    failed: '失败',
  }
  return labels[status]
}

function formatTokens(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(2)}M`
  if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(1)}K`
  return String(tokens)
}
</script>

<template>
  <section class="agent-command card">
    <header class="agent-command-head">
      <div>
        <p class="eyebrow">Agent Command Center</p>
        <h3>智能体执行链路</h3>
        <p>展示 Planner、Supervisor、Researcher、Quality Gate、Reviewer、Writer 的真实状态和产出。</p>
      </div>
      <div class="agent-command-score">
        <strong>{{ summary.completed_agents }}/{{ summary.total_agents }}</strong>
        <span>Agents completed</span>
      </div>
    </header>

    <div class="agent-summary-grid">
      <div class="agent-stat">
        <span>运行中</span>
        <b>{{ summary.running_agents }}</b>
      </div>
      <div class="agent-stat">
        <span>知识库命中</span>
        <b>{{ summary.knowledge_hits }}</b>
      </div>
      <div class="agent-stat">
        <span>证据来源</span>
        <b>{{ summary.source_count }}</b>
      </div>
      <div class="agent-stat">
        <span>Token</span>
        <b>{{ formatTokens(summary.total_tokens) }}</b>
      </div>
      <div class="agent-stat">
        <span>成本</span>
        <b>${{ summary.total_cost_usd.toFixed(4) }}</b>
      </div>
      <div class="agent-stat">
        <span>能力/工具</span>
        <b>{{ summary.capability_count }}/{{ summary.tool_count }}</b>
      </div>
    </div>

    <ElAlert v-if="error" class="agent-error" type="error" :closable="false" :title="error" />

    <div v-if="items.length" class="agent-trace-grid">
      <article
        v-for="agent in items"
        :key="agent.id"
        class="agent-card"
        :data-status="agent.status"
        :data-role="agent.role"
      >
        <div class="agent-card-head">
          <span class="agent-role">{{ agent.role }}</span>
          <span class="agent-status">{{ statusLabel(agent.status) }}</span>
        </div>
        <h4>{{ agent.title }}</h4>
        <div class="agent-autonomy">{{ agent.autonomy_level }}</div>
        <p class="agent-objective">{{ agent.objective }}</p>
        <div class="agent-tags">
          <span v-for="capability in agent.capabilities" :key="capability" class="agent-tag">
            {{ capability }}
          </span>
        </div>
        <dl class="agent-io">
          <div>
            <dt>输入</dt>
            <dd>{{ agent.input_summary || '等待上游输入' }}</dd>
          </div>
          <div>
            <dt>输出</dt>
            <dd>{{ agent.output_summary || '尚未产生输出' }}</dd>
          </div>
          <div>
            <dt>下一步</dt>
            <dd>{{ agent.next_action }}</dd>
          </div>
        </dl>
        <div class="agent-metrics">
          <span>来源 <b>{{ agent.source_count }}</b></span>
          <span :class="{ hot: agent.knowledge_hits > 0 }">知识库 <b>{{ agent.knowledge_hits }}</b></span>
          <span>证据 <b>{{ agent.evidence_count }}</b></span>
          <span>Token <b>{{ formatTokens(agent.token_count) }}</b></span>
        </div>
        <div class="agent-tools">
          <span v-for="tool in agent.tools" :key="tool">{{ tool }}</span>
        </div>
      </article>
    </div>
    <ElEmpty v-else :image-size="58" description="选择或启动任务后显示智能体执行链路" />
  </section>
</template>
