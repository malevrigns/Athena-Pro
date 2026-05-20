<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

const props = defineProps<{
  data: { node: string; cost: number }[]
}>()

// 按 cost 降序,让最贵的节点显示在最上面
const sorted = computed(() =>
  [...props.data].sort((a, b) => a.cost - b.cost)  // 升序,因为 echarts 从下往上画
)

const option = computed(() => ({
  grid: { left: 80, right: 20, top: 10, bottom: 30 },
  xAxis: {
    type: 'value',
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#a8a29e', fontSize: 11, formatter: '${value}' },
    splitLine: { lineStyle: { color: '#f5f5f4', type: 'dashed' } },
  },
  yAxis: {
    type: 'category',
    data: sorted.value.map(d => d.node),
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#57534e', fontSize: 11 },
  },
  tooltip: {
    trigger: 'axis',
    formatter: (params: any) => `${params[0].name}$${params[0].value.toFixed(3)}`,
  },
  series: [{
    type: 'bar',
    data: sorted.value.map(d => d.cost),
    itemStyle: { color: '#fb923c', borderRadius: [0, 4, 4, 0] },
    barWidth: 14,
  }],
}))
</script>

<template>
  <div class="rounded-xl border border-stone-200 bg-white p-6">
    <h3 class="font-serif text-base text-stone-900 mb-4">按节点分布</h3>
    <VChart :option="option" autoresize style="height: 280px" />
  </div>
</template>