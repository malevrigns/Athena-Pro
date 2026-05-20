<script setup lang="ts">
import { CopyDocument, Download, Right, CloseBold } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useTaskStore } from '@/stores/task'

const task = useTaskStore()

async function copyTaskId() {
  if (!task.current?.id) return
  await navigator.clipboard.writeText(task.current.id)
  ElMessage.success('Task ID 已复制')
}
async function copyReport() {
  if (!task.finalReport?.markdown) return
  await navigator.clipboard.writeText(task.finalReport.markdown)
  ElMessage.success('报告 Markdown 已复制')
}
async function exportMd() {
  if (!task.current?.id) return
  try { await task.downloadReport('md'); ElMessage.success('已下载 Markdown') }
  catch (e) { ElMessage.error((e as Error).message) }
}
</script>

<template>
  <div class="command-bar">
    <span class="cmd-key">⌘K</span>
    <strong>Command Center</strong>
    <ElButtonGroup size="small">
      <ElButton :icon="Right" :disabled="!task.current" @click="copyTaskId">复制 Task ID</ElButton>
      <ElButton :icon="CopyDocument" :disabled="!task.finalReport" @click="copyReport">复制报告</ElButton>
      <ElButton :icon="Download" :disabled="!task.finalReport" @click="exportMd">导出 MD</ElButton>
      <ElButton :icon="CloseBold" :disabled="!task.isRunning" type="danger" plain @click="task.stop()">中断</ElButton>
    </ElButtonGroup>
  </div>
</template>

<style scoped>
.command-bar {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px;
  border: 1px solid var(--athena-border);
  border-radius: 12px;
  background: var(--athena-surface);
  box-shadow: var(--athena-shadow-sm);
}
.cmd-key {
  display: inline-grid; place-items: center;
  min-width: 36px; height: 24px;
  border-radius: 6px;
  background: var(--athena-text);
  color: white;
  font-family: var(--athena-mono);
  font-size: 11px;
}
</style>
