<script setup lang="ts">
import type { ResearchPlan } from '@/types/api'
defineProps<{ plan: ResearchPlan | null }>()
</script>

<template>
  <section class="card plan-card">
    <div class="card-head"><strong>研究计划</strong><span>{{ plan?.topics.length || 0 }} topics</span></div>
    <div v-if="plan" class="topic-grid">
      <article v-for="topic in plan.topics" :key="topic.id" class="topic-card">
        <small>priority {{ topic.priority }}</small>
        <h3>{{ topic.title }}</h3>
        <p>{{ topic.question }}</p>
      </article>
    </div>
    <p v-else class="empty">等待 Planner 输出计划。</p>
  </section>
</template>
