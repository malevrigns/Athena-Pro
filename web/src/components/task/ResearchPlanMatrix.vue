<script setup lang="ts">
import type { ResearchPlan } from '@/types/api'

defineProps<{ plan: ResearchPlan | null }>()

function priorityColor(p: number) {
  if (p === 1) return ''           // primary
  if (p === 2) return 'success'
  if (p === 3) return 'warning'
  return 'info'
}
</script>

<template>
  <ElCard shadow="never" class="athena-card">
    <template #header>
      <div class="athena-card-head">
        <div>
          <div class="title"><strong>研究计划矩阵</strong></div>
          <p class="subtitle">Planner 拆解的子主题 · Reviewer 补研也会追加在这里</p>
        </div>
        <ElTag round size="small" type="primary" effect="light">{{ plan?.topics.length ?? 0 }} topics</ElTag>
      </div>
    </template>

    <ElEmpty v-if="!plan || !plan.topics.length" description="提交任务后, Planner 会拆出 3-5 个并行调研方向" :image-size="64" />
    <div v-else class="topic-list">
      <article v-for="topic in plan.topics" :key="topic.id" class="topic-card">
        <div class="rank">
          <span>{{ topic.priority }}</span>
          <small>P</small>
        </div>
        <div class="content">
          <div class="row-head">
            <code>{{ topic.id }}</code>
            <ElTag :type="priorityColor(topic.priority)" size="small" round effect="plain">优先级 {{ topic.priority }}</ElTag>
          </div>
          <h3>{{ topic.title }}</h3>
          <p>{{ topic.question }}</p>
          <p v-if="topic.rationale" class="rationale">动机: {{ topic.rationale }}</p>
          <div class="queries">
            <ElTag
              v-for="query in topic.search_queries"
              :key="query"
              size="small"
              effect="light"
              type="info"
              round
            >{{ query }}</ElTag>
          </div>
        </div>
      </article>
    </div>
  </ElCard>
</template>

<style scoped>
.topic-list { display: grid; gap: 12px; }
.topic-card {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr);
  gap: 14px;
  padding: 14px;
  border: 1px solid var(--athena-border);
  border-radius: 10px;
  background: var(--athena-surface-soft);
  transition: all .15s ease;
}
.topic-card:hover {
  border-color: var(--el-color-primary-light-7);
  box-shadow: var(--athena-shadow-sm);
  transform: translateY(-1px);
}
.rank {
  width: 56px; min-height: 64px;
  display: grid; place-items: center;
  border-radius: 8px;
  background: var(--athena-gradient);
  color: #fff;
  font-family: var(--athena-mono);
  box-shadow: 0 6px 18px rgba(124,58,237,.3);
}
.rank span { font-size: 22px; font-weight: 800; line-height: 1; }
.rank small { font-size: 10px; letter-spacing: .12em; opacity: .8; }

.row-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.row-head code {
  font-family: var(--athena-mono);
  font-size: 11px;
  color: var(--athena-muted);
  background: var(--athena-surface);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--athena-border);
}
.content h3 { margin: 4px 0 6px; font-size: 14.5px; font-weight: 600; color: var(--athena-text); }
.content p { margin: 0 0 6px; color: var(--athena-text-soft); font-size: 13px; line-height: 1.55; }
.rationale { color: var(--athena-muted) !important; font-size: 12px !important; }
.queries { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
</style>
