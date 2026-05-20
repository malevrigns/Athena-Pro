<script setup lang="ts">
import { onBeforeUnmount } from 'vue'
import { useTaskStore } from '@/stores/task'
import TaskStream from '@/components/task/TaskStream.vue'

// 路由 props: true 让 :id 直接当 prop
defineProps<{ id: string }>()

const taskStore = useTaskStore()

// 离开页面时清空 store(防止下次进来看到旧任务残影)
onBeforeUnmount(() => taskStore.reset())
</script>

<template>
  <TaskStream :task-id="id" />
</template>