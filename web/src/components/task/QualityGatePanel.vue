<script setup lang="ts">
import { computed } from 'vue'
import type { QualityScore } from '@/types/api'

const props = defineProps<{ quality: QualityScore | null }>()

const metrics = computed(() => {
  const q = props.quality
  return [
    { key: 'factuality', label: '事实一致性', value: q?.factuality ?? 0 },
    { key: 'coverage', label: '覆盖度', value: q?.coverage ?? 0 },
    { key: 'citation_integrity', label: '引用完整性', value: q?.citation_integrity ?? 0 },
    { key: 'contradiction_risk', label: '矛盾风险 (越低越好)', value: q?.contradiction_risk ?? 0, danger: true },
  ]
})

const overall = computed(() => props.quality?.overall ?? 0)
const overallStatus = computed(() => {
  const v = overall.value
  if (v >= 0.8) return 'success'
  if (v >= 0.6) return ''
  if (v >= 0.4) return 'warning'
  return 'exception'
})
</script>

<template>
  <ElCard shadow="never" class="athena-card">
    <template #header>
      <div class="athena-card-head">
        <div>
          <div class="title"><strong>质量门控</strong></div>
          <p class="subtitle">FactChecker + CitationValidator · 不达标自动触发 Reviewer 补研</p>
        </div>
        <ElTag round size="small" :type="overallStatus === 'exception' ? 'danger' : overallStatus === 'warning' ? 'warning' : overallStatus === 'success' ? 'success' : 'primary'">
          总分 {{ (overall * 100).toFixed(0) }}%
        </ElTag>
      </div>
    </template>

    <div v-if="quality" class="metric-list">
      <div v-for="m in metrics" :key="m.key" class="metric-row">
        <div class="metric-head">
          <span>{{ m.label }}</span>
          <b>{{ (m.value * 100).toFixed(0) }}%</b>
        </div>
        <ElProgress
          :percentage="m.value * 100"
          :stroke-width="6"
          :show-text="false"
          :status="m.danger && m.value > 0.5 ? 'exception' : m.value >= 0.7 ? 'success' : undefined"
        />
      </div>

      <div class="overall">
        <span class="overall-label">综合质量</span>
        <ElProgress
          :percentage="overall * 100"
          :stroke-width="14"
          :status="overallStatus === 'exception' ? 'exception' : overallStatus === 'warning' ? 'warning' : overallStatus === 'success' ? 'success' : undefined"
          striped
          striped-flow
        />
      </div>

      <ul v-if="quality.notes?.length" class="quality-notes">
        <li v-for="note in quality.notes" :key="note">{{ note }}</li>
      </ul>
    </div>
    <ElEmpty v-else description="完成 quality_gate 节点后展示评分" :image-size="64" />
  </ElCard>
</template>

<style scoped>
.metric-list { display: grid; gap: 12px; }
.metric-row { display: grid; gap: 4px; }
.metric-head {
  display: flex; justify-content: space-between;
  font-size: 13px; color: var(--athena-text-soft);
}
.metric-head b { color: var(--athena-text); font-weight: 600; }
.overall { margin-top: 6px; padding-top: 12px; border-top: 1px dashed var(--athena-border); }
.overall-label { display: block; margin-bottom: 6px; font-size: 12px; color: var(--athena-muted); text-transform: uppercase; letter-spacing: .08em; font-family: var(--athena-mono); }
.quality-notes {
  margin: 12px 0 0; padding-left: 18px;
  color: var(--athena-muted);
  font-size: 12.5px; line-height: 1.65;
}
</style>
