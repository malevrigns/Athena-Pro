<script setup lang="ts">
import { onMounted } from 'vue'
import { useCostStore } from '@/stores/cost'
import { apiClient } from '@/api/client'
import MonthlyCostLine from '@/components/cost/MonthlyCostLine.vue'
import CostByModelPie from '@/components/cost/CostByModelPie.vue'
import CostByNodeBars from '@/components/cost/CostByNodeBars.vue'

const store = useCostStore()

onMounted(async () => {
  const data = await apiClient.getMonthlyCost()
  store.setMonthly(data)
})
</script>

<template>
  <div class="max-w-6xl mx-auto py-10 px-6">
    <h1 class="font-serif text-3xl text-stone-900 mb-1">成本仪表盘</h1>
    <p class="text-sm text-stone-600 mb-8">
      本月你的所有任务的成本明细
    </p>

    <div v-if="store.monthly" class="grid grid-cols-12 gap-6">
      <div class="col-span-8">
        <MonthlyCostLine :data="store.monthly.daily" />
      </div>
      <div class="col-span-4">
        <CostByModelPie :data="store.monthly.by_model" />
      </div>
      <div class="col-span-12">
        <CostByNodeBars :data="store.monthly.by_node" />
      </div>
    </div>
  </div>
</template>