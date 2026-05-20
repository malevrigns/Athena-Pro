<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, LegendComponent,
  TitleComponent, DatasetComponent, MarkLineComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart, BarChart, PieChart,
  GridComponent, TooltipComponent, LegendComponent,
  TitleComponent, DatasetComponent, MarkLineComponent,
  CanvasRenderer,
])

const props = defineProps<{ option: any; height?: string }>()
const el = ref<HTMLDivElement | null>(null)
let instance: echarts.ECharts | null = null

function resize() { instance?.resize() }

onMounted(() => {
  if (!el.value) return
  instance = echarts.init(el.value, undefined, { renderer: 'canvas' })
  instance.setOption(props.option)
  window.addEventListener('resize', resize)
})

watch(() => props.option, (o) => instance?.setOption(o, true), { deep: true })

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  instance?.dispose()
  instance = null
})
</script>

<template>
  <div ref="el" :style="{ width: '100%', height: height || '240px' }" />
</template>
