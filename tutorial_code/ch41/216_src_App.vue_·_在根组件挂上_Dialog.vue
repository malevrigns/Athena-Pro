<script setup lang="ts">
import { NConfigProvider, NMessageProvider, NDialogProvider } from 'naive-ui'
import PermissionDialog from '@/components/permission/PermissionDialog.vue'
</script>

<template>
  <NConfigProvider>
    <NMessageProvider>
      <NDialogProvider>
        <RouterView />
        <!-- 全局挂载,跟路由无关 -->
        <PermissionDialog />
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>