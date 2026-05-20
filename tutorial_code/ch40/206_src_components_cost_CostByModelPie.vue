<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, PieChart, TooltipComponent, LegendComponent])

const COLORS = ['#fb923c', '#fbbf24', '#a3e635', '#22d3ee', '#a78bfa']

const props = defineProps<{
  data: { model: string; cost: number }[]
}>()

const option = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (p: any) => `${p.name}$${p.value.toFixed(3)} (${p.percent}%)`,
  },
  legend: {
    bottom: 0,
    icon: 'circle',
    textStyle: { color: '#57534e', fontSize: 11 },
    itemWidth: 10,
    itemHeight: 10,
    itemGap: 14,
  },
  series: [{
    type: 'pie',
    radius: ['45%', '70%'],
    center: ['50%', '42%'],
    avoidLabelOverlap: false,
    label: { show: false },
    labelLine: { show: false },
    data: props.data.map((d, i) => ({
      value: d.cost,
      name: d.model,
      itemStyle: { color: COLORS[i % COLORS.length] },
    })),
  }],
}))
</script>

<template>
  <div class="rounded-xl border border-stone-200 bg-white p-6">
    <h3 class="font-serif text-base text-stone-900 mb-4">按模型分布</h3>
    <VChart :option="option" autoresize style="height: 240px" />
  </div>
</template>