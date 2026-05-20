<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, TitleComponent,
} from 'echarts/components'

// 按需注册 echarts 模块(否则 bundle 会带全套 ~2MB)
use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, TitleComponent])

const props = defineProps<{
  data: { date: string; cost: number }[]
}>()

const latestCost = computed(() => {
  if (!props.data.length) return 0
  return props.data[props.data.length - 1].cost
})

const option = computed(() => ({
  grid: { left: 40, right: 12, top: 20, bottom: 30 },
  xAxis: {
    type: 'category',
    data: props.data.map(d => d.date),
    axisLine: { lineStyle: { color: '#e7e5e4' } },
    axisLabel: { color: '#a8a29e', fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#a8a29e', fontSize: 11, formatter: '${value}' },
    splitLine: { lineStyle: { color: '#f5f5f4', type: 'dashed' } },
  },
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#ffffff',
    borderColor: '#e7e5e4',
    textStyle: { color: '#1c1917', fontSize: 12 },
    formatter: (params: any) => {
      const p = params[0]
      return `${p.name}累计 $${p.value.toFixed(3)}`
    },
  },
  series: [{
    type: 'line',
    smooth: true,
    symbol: 'none',
    data: props.data.map(d => d.cost),
    lineStyle: { color: '#fb923c', width: 2 },
    areaStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(251, 146, 60, 0.25)' },
          { offset: 1, color: 'rgba(251, 146, 60, 0)' },
        ],
      },
    },
  }],
}))
</script>

<template>
  <div class="rounded-xl border border-stone-200 bg-white p-6">
    <h3 class="font-serif text-base text-stone-900 mb-1">本月累计成本</h3>
    <p class="text-3xl font-semibold text-stone-900 mb-4">
      ${{ latestCost.toFixed(2) }}
    </p>
    <VChart :option="option" autoresize style="height: 180px" />
  </div>
</template>